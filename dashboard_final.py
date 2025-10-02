# CÓDIGO MAESTRO DEFINITIVO Y "A PRUEBA DE BALAS"

import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Plataforma de Trading", page_icon="🏦", layout="wide")

# --- ESTILOS CSS ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stApp { background-color: #0B0F19; }
    .stRadio > label { font-size: 1.2em; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES AUXILIARES ---
@st.cache_data
def cargar_transacciones():
    if os.path.exists("transacciones.csv"):
        try: return pd.read_csv("transacciones.csv", parse_dates=['Fecha'])
        except: return pd.DataFrame(columns=["Tipo", "Ticker", "Cantidad", "Precio", "Fecha"])
    return pd.DataFrame(columns=["Tipo", "Ticker", "Cantidad", "Precio", "Fecha"])

def guardar_transacciones(df):
    df.to_csv("transacciones.csv", index=False)

@st.cache_data
def cargar_lista_tickers_gbm():
    if not os.path.exists("tickers_gbm.csv"): return None
    try:
        df = pd.read_csv("tickers_gbm.csv")
        df['Display'] = df['Name'] + " (" + df['User_Ticker'] + ") - " + df['Market']
        return df
    except: return None

@st.cache_data(ttl=3600)
def get_stock_info_cached(api_ticker):
    try:
        stock = yf.Ticker(api_ticker)
        info = stock.info
        if info and info.get('symbol'):
            try: info['calendar'] = stock.calendar.to_dict()
            except: info['calendar'] = {}
            return info
        return {}
    except: return {}

@st.cache_data(ttl=600)
def create_candlestick_chart(api_ticker):
    data = yf.download(api_ticker, period="6mo", interval="1d", progress=False)
    if data.empty: return None
    fig = go.Figure(data=[go.Candlestick(x=data.index, open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'])])
    fig.update_layout(title_text=f'Gráfica de {api_ticker}', template='plotly_dark', xaxis_rangeslider_visible=False)
    return fig

# --- INICIALIZACIÓN DE ESTADO ---
if 'transactions' not in st.session_state: st.session_state.transactions = cargar_transacciones()
if 'page' not in st.session_state: st.session_state.page = 'Portafolio'
if 'ticker_to_trade' not in st.session_state: st.session_state.ticker_to_trade = None
lista_tickers_df = cargar_lista_tickers_gbm()

# --- BARRA DE NAVEGACIÓN LATERAL ---
with st.sidebar:
    st.title("Plataforma de Inversión")
    st.session_state.page = st.radio("Menú Principal", ('Portafolio', 'Operar', 'Explorador', 'Noticias'))

# --- CONTENIDO PRINCIPAL BASADO EN LA NAVEGACIÓN ---

# --- PÁGINA 1: PORTAFOLIO ---
if st.session_state.page == 'Portafolio':
    st.header("Análisis de Rendimiento del Portafolio")
    try:
        if st.session_state.transactions.empty:
            st.info("Bienvenido. Agrega una transacción en la página 'Operar'.")
        else:
            df_trades = st.session_state.transactions[st.session_state.transactions['Tipo'].isin(['Compra', 'Venta'])]
            portfolio = {}
            if not df_trades.empty:
                for ticker in df_trades['Ticker'].unique():
                    df_ticker = df_trades[df_trades['Ticker'] == ticker]
                    qty = df_ticker[df_ticker['Tipo']=='Compra']['Cantidad'].sum() - df_ticker[df_ticker['Tipo']=='Venta']['Cantidad'].sum()
                    if qty > 1e-6:
                        compras = df_ticker[df_ticker['Tipo']=='Compra']
                        if compras['Cantidad'].sum() > 0:
                            avg_cost = (compras['Cantidad'] * compras['Precio']).sum() / compras['Cantidad'].sum()
                            portfolio[ticker] = {'Cantidad': qty, 'Costo Total': qty * avg_cost, 'Precio Promedio Compra': avg_cost}
            
            if portfolio:
                portfolio_df = pd.DataFrame.from_dict(portfolio, orient='index').reset_index().rename(columns={'index': 'API_Ticker'})
                def get_best_price(t): return (get_stock_info_cached(t).get('currentPrice') or get_stock_info_cached(t).get('previousClose') or 0)
                portfolio_df['Precio Actual'] = portfolio_df['API_Ticker'].apply(get_best_price)
                portfolio_df['Valor de Mercado'] = portfolio_df['Cantidad'] * portfolio_df['Precio Actual']
                if lista_tickers_df is not None:
                    portfolio_df = pd.merge(portfolio_df, lista_tickers_df[['API_Ticker', 'Market']], on='API_Ticker', how='left')
                portfolio_df['Market'] = portfolio_df['Market'].fillna('Desconocido')
                def get_sector(t): return get_stock_info_cached(t).get('sector', 'No Clasificado')
                portfolio_df['Sector'] = portfolio_df['API_Ticker'].apply(get_sector)

                st.subheader("Análisis de Diversificación")
                total_market_value = portfolio_df['Valor de Mercado'].sum()
                if total_market_value > 0:
                    c1, c2 = st.columns(2)
                    with c1: st.plotly_chart(px.pie(portfolio_df, values='Valor de Mercado', names='Market', title='Asignación por Mercado'), use_container_width=True)
                    with c2: st.plotly_chart(px.pie(portfolio_df, values='Valor de Mercado', names='Sector', title='Asignación por Sector'), use_container_width=True)
                
                st.subheader("Detalle de Posiciones"); st.dataframe(portfolio_df, use_container_width=True)
            else:
                st.info("Aún no tienes posiciones abiertas.")
    except Exception as e:
        st.error("Ocurrió un error en la página 'Portafolio'."); st.exception(e)

# --- PÁGINA 2: OPERAR ---
elif st.session_state.page == 'Operar':
    st.header("Centro de Trading")
    try:
        if lista_tickers_df is None:
            st.error("No se pudo cargar 'tickers_gbm.csv'.")
        else:
            opcion = st.selectbox("Busca un activo para operar", options=lista_tickers_df['Display'], index=None, placeholder="Escribe para buscar...")
            if opcion:
                fila = lista_tickers_df[lista_tickers_df['Display'] == opcion]
                if not fila.empty:
                    st.session_state.ticker_to_trade = {'user': fila['User_Ticker'].iloc[0], 'api': fila['API_Ticker'].iloc[0]}
            
            if st.session_state.ticker_to_trade:
                api_ticker, user_ticker = st.session_state.ticker_to_trade['api'], st.session_state.ticker_to_trade['user']
                st.write("---")
                col_chart, col_form = st.columns([3, 1])
                with col_chart:
                    st.subheader(f"Gráfica de {user_ticker}")
                    with st.spinner("Cargando gráfica..."):
                        fig = create_candlestick_chart(api_ticker)
                        if fig: st.plotly_chart(fig, use_container_width=True)
                        else: st.warning("No se pudieron obtener datos para la gráfica.")
                with col_form:
                    st.subheader("Boleta de Operación")
                    with st.form(key=f"form_{user_ticker}"):
                        tipo_op, qty, price, date = st.radio("Operación", ["Compra", "Venta"]), st.number_input("Títulos"), st.number_input("Precio"), st.date_input("Fecha")
                        if st.form_submit_button(f"Ejecutar {tipo_op}", use_container_width=True):
                            if qty > 0 and price > 0:
                                new_tx = pd.DataFrame([{"Tipo": tipo_op, "Ticker": api_ticker, "Cantidad": qty, "Precio": price, "Fecha": pd.to_datetime(date)}])
                                st.session_state.transactions = pd.concat([st.session_state.transactions, new_tx], ignore_index=True)
                                guardar_transacciones(st.session_state.transactions)
                                st.success(f"¡Operación registrada para {user_ticker}!")
                            else: st.error("La cantidad y el precio deben ser mayores a cero.")
            else:
                st.info("Selecciona un activo en la barra de búsqueda para comenzar a operar.")
    except Exception as e:
        st.error("Ocurrió un error en la página 'Operar'."); st.exception(e)

# --- PÁGINA 3: EXPLORADOR ---
elif st.session_state.page == 'Explorador':
    st.header("Explorador de Acciones")
    try:
        if lista_tickers_df is not None:
            opcion_exp = st.selectbox("Selecciona una acción para explorar", options=lista_tickers_df['Display'], index=None, key="exp_select")
            if opcion_exp:
                fila_exp = lista_tickers_df[lista_tickers_df['Display'] == opcion_exp]
                if not fila_exp.empty:
                    api_ticker_exp, user_ticker_exp = fila_exp['API_Ticker'].iloc[0], fila_exp['User_Ticker'].iloc[0]
                    with st.spinner(f"Cargando {user_ticker_exp}..."): info = get_stock_info_cached(api_ticker_exp)
                    if info: st.json(info)
                    else: st.error(f"No se pudo obtener información para {api_ticker_exp}.")
        else:
            st.error("No se pudo cargar 'tickers_gbm.csv'.")
    except Exception as e:
        st.error("Ocurrió un error en la página 'Explorador'."); st.exception(e)

# --- PÁGINA 4: NOTICIAS ---
elif st.session_state.page == 'Noticias':
    st.header("Últimas Noticias de tus Inversiones")
    try:
        # Se necesita volver a calcular el portfolio_df aquí si no se ha visitado el dashboard antes
        df_trades = st.session_state.transactions[st.session_state.transactions['Tipo'].isin(['Compra', 'Venta'])]
        portfolio_tickers = []
        if not df_trades.empty:
            for ticker in df_trades['Ticker'].unique():
                qty = df_trades[df_trades['Ticker']==ticker]['Cantidad'].sum()
                if qty > 1e-6: portfolio_tickers.append(ticker)
        
        if portfolio_tickers:
            with st.spinner("Buscando noticias..."):
                all_news, seen_links = [], set()
                for ticker in portfolio_tickers:
                    try:
                        news = yf.Ticker(ticker).news
                        for article in news:
                            if 'link' in article and article['link'] not in seen_links:
                                all_news.append(article); seen_links.add(article['link'])
                    except: pass
                all_news.sort(key=lambda x: x.get('providerPublishTime', 0), reverse=True)
                if all_news:
                    for article in all_news[:20]: st.markdown(f"**[{article.get('title')}]({article.get('link')})** - *{article.get('publisher')}*")
                else: st.info("No se encontraron noticias recientes para tu portafolio.")
        else:
            st.info("Aún no tienes posiciones abiertas para mostrar noticias.")
    except Exception as e:
        st.error("Error en 'Noticias'"); st.exception(e)