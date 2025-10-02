# =============================================================================
# CÓDIGO MAESTRO FINAL Y ABSOLUTO - TODAS LAS FUNCIONALIDADES INTEGRADAS
# =============================================================================

import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os
import investpy

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Plataforma de Trading", page_icon="🏦", layout="wide")

# --- 2. IMPLEMENTACIÓN DE SEGURIDAD ---
def check_password():
    if st.session_state.get("password_correct", False): return True
    st.title("Plataforma de Inversión")
    st.write("Por favor, introduce la contraseña para acceder.")
    password_input = st.text_input("Contraseña", type="password", key="password_input_widget")
    if st.button("Acceder"):
        if password_input and password_input == st.secrets.get("password", ""):
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("😕 Contraseña incorrecta.")
    return False

# --- 3. LA APLICACIÓN COMPLETA SOLO SE EJECUTA SI LA CONTRASEÑA ES CORRECTA ---
if check_password():

    # --- ESTILOS CSS ---
    st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} .stApp { background-color: #0B0F19; }</style>""", unsafe_allow_html=True)

    # --- FUNCIONES AUXILIARES ---
    @st.cache_data
    def cargar_transacciones():
        if os.path.exists("transacciones.csv"):
            try: return pd.read_csv("transacciones.csv", parse_dates=['Fecha'])
            except: return pd.DataFrame(columns=["Tipo", "Ticker", "Cantidad", "Precio", "Fecha"])
        return pd.DataFrame(columns=["Tipo", "Ticker", "Cantidad", "Precio", "Fecha"])

    def guardar_transacciones(df):
        df.to_csv("transacciones.csv", index=False)

    @st.cache_data(ttl=86400)
    def cargar_lista_tickers_web():
        try:
            stocks_mx = investpy.get_stocks(country='mexico')[['symbol', 'name']]
            stocks_mx.columns = ['User_Ticker', 'Name']
            stocks_mx['API_Ticker'] = stocks_mx['User_Ticker'] + '.MX'
            stocks_mx['Market'] = 'BMV'
            stocks_us = investpy.get_stocks(country='united states')[['symbol', 'name']]
            stocks_us.columns = ['User_Ticker', 'Name']
            stocks_us['API_Ticker'] = stocks_us['User_Ticker']
            stocks_us['Market'] = 'SIC'
            df = pd.concat([stocks_mx, stocks_us], ignore_index=True).dropna().drop_duplicates(subset=['User_Ticker'])
            df['Display'] = df['Name'] + " (" + df['User_Ticker'] + ") - " + df['Market']
            return df
        except Exception as e:
            raise RuntimeError(f"No se pudo descargar la lista de tickers: {e}.")

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

    def format_large_number(num):
        if num is None or not isinstance(num, (int, float)): return "N/A"
        if num > 1_000_000_000_000: return f"{num / 1_000_000_000_000:.2f} T"
        if num > 1_000_000_000: return f"{num / 1_000_000_000:.2f} B"
        if num > 1_000_000: return f"{num / 1_000_000:.2f} M"
        return f"{num:,.2f}"

    # --- INICIALIZACIÓN DE ESTADO Y DATOS ---
    if 'transactions' not in st.session_state: st.session_state.transactions = cargar_transacciones()
    if 'page' not in st.session_state: st.session_state.page = 'Portafolio'
    if 'ticker_to_trade' not in st.session_state: st.session_state.ticker_to_trade = None
    
    lista_tickers_df = None
    try:
        with st.spinner("Actualizando lista de tickers del mercado..."):
            lista_tickers_df = cargar_lista_tickers_web()
    except Exception as e:
        st.error(e)

    # --- BARRA DE NAVEGACIÓN LATERAL ---
    with st.sidebar:
        st.title("Plataforma de Inversión")
        st.session_state.page = st.radio("Menú Principal", ('Portafolio', 'Operar', 'Explorador', 'Noticias'))
    
    # --- PÁGINA 1: PORTAFOLIO ---
    if st.session_state.page == 'Portafolio':
        st.header("Análisis de Rendimiento del Portafolio")
        try:
            if st.session_state.transactions.empty:
                st.info("Bienvenido. Agrega una transacción en la página 'Operar'.")
            else:
                portfolio_df = pd.DataFrame()
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
                    def get_best_price(t): info = get_stock_info_cached(t); return info.get('currentPrice', info.get('previousClose', 0)) or 0
                    portfolio_df['Precio Actual'] = portfolio_df['API_Ticker'].apply(get_best_price)
                    portfolio_df['Valor de Mercado'] = portfolio_df['Cantidad'] * portfolio_df['Precio Actual']
                    portfolio_df['Ganancia/Pérdida ($)'] = portfolio_df['Valor de Mercado'] - portfolio_df['Costo Total']
                    portfolio_df['Ganancia/Pérdida (%)'] = (portfolio_df['Ganancia/Pérdida ($)'] / portfolio_df['Costo Total']).replace([float('inf'), -float('inf')], 0) * 100
                    
                    st.subheader("Resumen General")
                    total_market_value, total_cost_basis = portfolio_df['Valor de Mercado'].sum(), portfolio_df['Costo Total'].sum()
                    total_gain_loss = total_market_value - total_cost_basis
                    total_return_pct = (total_gain_loss / total_cost_basis) * 100 if total_cost_basis > 0 else 0
                    c1,c2,c3 = st.columns(3); c1.metric("Valor del Portafolio",f"${total_market_value:,.2f}"); c2.metric("Inversión Total",f"${total_cost_basis:,.2f}"); c3.metric("Utilidad Neta Total",f"${total_gain_loss:,.2f}",f"{total_return_pct:.2f}%")

                    st.subheader("Ganancia y Pérdida por Activo")
                    portfolio_df_sorted = portfolio_df.sort_values('Ganancia/Pérdida ($)')
                    portfolio_df_sorted['Color'] = ['Ganancia' if g >= 0 else 'Pérdida' for g in portfolio_df_sorted['Ganancia/Pérdida ($)']]
                    fig_gpl = px.bar(portfolio_df_sorted, x='Ganancia/Pérdida ($)', y='API_Ticker', orientation='h', color='Color', color_discrete_map={'Ganancia':'green', 'Pérdida':'red'})
                    st.plotly_chart(fig_gpl, use_container_width=True)
                    
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
                st.error("La lista de tickers no está disponible. No se puede operar.")
            else:
                opcion = st.selectbox("Busca un activo para operar", options=lista_tickers_df['Display'], index=None, placeholder="Escribe para buscar...")
                if opcion:
                    fila = lista_tickers_df[lista_tickers_df['Display'] == opcion]
                    if not fila.empty: st.session_state.ticker_to_trade = {'user': fila['User_Ticker'].iloc[0], 'api': fila['API_Ticker'].iloc[0]}
                
                if st.session_state.ticker_to_trade:
                    api_ticker, user_ticker = st.session_state.ticker_to_trade['api'], st.session_state.ticker_to_trade['user']
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
        st.header("Explorador de Activos")
        try:
            if lista_tickers_df is not None:
                opcion_exp = st.selectbox("Selecciona una acción para analizar", options=lista_tickers_df['Display'], index=None, placeholder="Escribe para buscar...")
                if opcion_exp:
                    fila_exp = lista_tickers_df[lista_tickers_df['Display'] == opcion_exp]
                    if not fila_exp.empty:
                        api_ticker_exp = fila_exp['API_Ticker'].iloc[0]
                        with st.spinner(f"Cargando datos para {api_ticker_exp}..."): info = get_stock_info_cached(api_ticker_exp)
                        if info:
                            st.subheader(f"{info.get('longName', api_ticker_exp)}")
                            st.write(f"**{info.get('symbol', '')}** | {info.get('sector', 'N/A')} | {info.get('industry', 'N/A')}")
                            with st.expander("Resumen del Negocio"): st.write(info.get('longBusinessSummary', 'No hay resumen.'))
                            st.subheader("Métricas de Mercado")
                            c1, c2, c3, c4 = st.columns(4)
                            c1.metric("Precio Actual", f"${info.get('currentPrice', 0):,.2f}"); c2.metric("Capitalización", format_large_number(info.get('marketCap'))); c3.metric("Volumen", format_large_number(info.get('volume'))); c4.metric("Ratio P/E", f"{info.get('trailingPE', 0):,.2f}")
                            st.subheader("Análisis de Ratios Financieros")
                            col1, col2 = st.columns(2)
                            with col1:
                                valuation_metrics = {'P/E': info.get('trailingPE'), 'Precio/Ventas': info.get('priceToSalesTrailing12Months'), 'Precio/Libro': info.get('priceToBook'), 'Empresa/EBITDA': info.get('enterpriseToEbitda')}
                                if valuation_metrics := {k: v for k, v in valuation_metrics.items() if v is not None}:
                                    st.plotly_chart(px.bar(pd.DataFrame(list(valuation_metrics.items()), columns=['Métrica', 'Valor']), x='Valor', y='Métrica', orientation='h', title='Ratios de Valuación'), use_container_width=True)
                            with col2:
                                profitability_metrics = {'Margen Neto (%)': (info.get('profitMargins') or 0)*100, 'ROA (%)': (info.get('returnOnAssets') or 0)*100, 'ROE (%)': (info.get('returnOnEquity') or 0)*100}
                                if profitability_metrics := {k: v for k, v in profitability_metrics.items() if v is not None}:
                                    st.plotly_chart(px.bar(pd.DataFrame(list(profitability_metrics.items()), columns=['Métrica', 'Valor']), x='Valor', y='Métrica', orientation='h', title='Ratios de Rentabilidad'), use_container_width=True)
                        else: st.error(f"No se pudo obtener información para {api_ticker_exp}.")
            else:
                st.error("No se pudo cargar la lista de tickers.")
        except Exception as e:
            st.error("Ocurrió un error en la página 'Explorador'."); st.exception(e)

    # --- PÁGINA 4: NOTICIAS ---
    elif st.session_state.page == 'Noticias':
        st.header("Últimas Noticias de tus Inversiones")
        try:
            if st.session_state.transactions.empty: st.info("Aún no tienes posiciones para mostrar noticias.")
            else:
                tickers_en_portafolio = st.session_state.transactions['Ticker'].unique().tolist()
                with st.spinner("Buscando noticias..."):
                    all_news, seen_links = [], set()
                    for ticker in tickers_en_portafolio:
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
        except Exception as e:
            st.error("Ocurrió un error en la página 'Noticias'."); st.exception(e)