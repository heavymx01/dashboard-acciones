import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard de Portafolio Pro", page_icon="🏦", layout="wide")

# --- ESTILOS CSS (CON VENTANA FLOTANTE CORREGIDA) ---
st.markdown("""
<style>
    /* --- Ventana Flotante --- */
    .floating-balance {
        position: fixed;
        top: 80px;       /* <-- POSICIÓN CORREGIDA */
        right: 20px;
        background-color: #1C212E;
        border: 1px solid #00d1b2;
        border-radius: 10px;
        padding: 15px 20px;
        z-index: 1000;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
        text-align: left;  /* <-- ALINEACIÓN CORREGIDA */
    }
    .floating-balance .label {
        font-size: 0.8em;
        color: #8A91A0;
        margin-bottom: 5px;
    }
    .floating-balance .value {
        font-size: 1.4em;
        font-weight: bold;
        color: #FAFAFA;
        margin: 0;
    }
    /* --- Otros estilos --- */
    div[data-testid*="stButton"] > button {
        border: 1px solid #2a3142; text-align: left !important; margin-bottom: 5px; width: 100%;
    }
    div[data-testid*="stButton"] > button:hover {
        border-color: #00d1b2; color: #00d1b2;
    }
</style>
""", unsafe_allow_html=True)


# --- FUNCIONES AUXILIARES ---
@st.cache_data
def cargar_transacciones():
    if os.path.exists("transacciones.csv"):
        try: return pd.read_csv("transacciones.csv", parse_dates=['Fecha'])
        except Exception as e: st.error(f"Error al leer transacciones.csv: {e}")
    return pd.DataFrame(columns=["Tipo", "Ticker", "Cantidad", "Precio", "Fecha"])

def guardar_transacciones(df):
    df.to_csv("transacciones.csv", index=False)

@st.cache_data
def cargar_lista_tickers_gbm():
    if not os.path.exists("tickers_gbm.csv"): return None
    try:
        df = pd.read_csv("tickers_gbm.csv")
        required_columns = ['User_Ticker', 'API_Ticker', 'Name', 'Market']
        if not all(col in df.columns for col in required_columns): return None
        df['Display'] = df['Name'] + " (" + df['User_Ticker'] + ") - " + df['Market']
        return df
    except Exception: return None

@st.cache_data(ttl=3600)
def get_stock_info_cached(api_ticker):
    try:
        stock = yf.Ticker(api_ticker)
        info = stock.info
        return info if info and info.get('symbol') else {}
    except Exception:
        return {}

# --- INICIALIZACIÓN ---
if 'transactions' not in st.session_state:
    st.session_state.transactions = cargar_transacciones()
if 'ticker_to_explore' not in st.session_state:
    st.session_state.ticker_to_explore = None
lista_tickers_df = cargar_lista_tickers_gbm()
total_market_value = 0.0

# --- PESTAÑAS ---
tabs = st.tabs(["📊 Dashboard", "📈 Operar", "🔍 Explorador", "📰 Noticias"])

# --- PESTAÑA 1: DASHBOARD ---
with tabs[0]:
    st.header("Análisis de Portafolio")
    try:
        if not st.session_state.transactions.empty:
            df_trades = st.session_state.transactions[st.session_state.transactions['Tipo'].isin(['Compra', 'Venta'])]
            portfolio = {}
            if not df_trades.empty:
                for ticker in df_trades['Ticker'].unique():
                    df_ticker = df_trades[df_trades['Ticker'] == ticker]
                    cantidad_total = df_ticker[df_ticker['Tipo']=='Compra']['Cantidad'].sum() - df_ticker[df_ticker['Tipo']=='Venta']['Cantidad'].sum()
                    if cantidad_total > 1e-6:
                        compras = df_ticker[df_ticker['Tipo']=='Compra']
                        if compras['Cantidad'].sum() > 0:
                            costo_promedio = (compras['Cantidad'] * compras['Precio']).sum() / compras['Cantidad'].sum()
                            portfolio[ticker] = {'Cantidad': cantidad_total, 'Costo Total': cantidad_total * costo_promedio}

            if portfolio:
                portfolio_df = pd.DataFrame.from_dict(portfolio, orient='index').reset_index().rename(columns={'index': 'API_Ticker'})
                def get_best_price(ticker):
                    info = get_stock_info_cached(ticker)
                    return info.get('currentPrice', info.get('previousClose', 0)) or 0
                portfolio_df['Precio Actual'] = portfolio_df['API_Ticker'].apply(get_best_price)
                portfolio_df['Valor de Mercado'] = portfolio_df['Cantidad'] * portfolio_df['Precio Actual']

                if lista_tickers_df is not None:
                    portfolio_df = pd.merge(portfolio_df, lista_tickers_df[['API_Ticker', 'Market']], on='API_Ticker', how='left')
                portfolio_df['Market'] = portfolio_df['Market'].fillna('Desconocido')
                
                def obtener_sector(ticker):
                    return get_stock_info_cached(ticker).get('sector', 'No Clasificado')
                portfolio_df['Sector'] = portfolio_df['API_Ticker'].apply(obtener_sector)
                
                total_market_value = portfolio_df['Valor de Mercado'].sum()
                if total_market_value > 0:
                    st.subheader("Análisis de Diversificación")
                    col1, col2 = st.columns(2)
                    with col1:
                        fig_market = px.pie(portfolio_df, values='Valor de Mercado', names='Market', title='Asignación por Mercado', color_discrete_sequence=px.colors.sequential.Teal)
                        st.plotly_chart(fig_market, use_container_width=True)
                    with col2:
                        fig_sector = px.pie(portfolio_df, values='Valor de Mercado', names='Sector', title='Asignación por Sector', color_discrete_sequence=px.colors.sequential.Plasma)
                        st.plotly_chart(fig_sector, use_container_width=True)
                
                st.subheader("Detalle de Posiciones")
                st.dataframe(portfolio_df, use_container_width=True)
        else:
            st.info("Bienvenido. Dirígete a la pestaña 'Operar' para agregar tu primera transacción.")
    except Exception as e:
        st.error("Ocurrió un error en la pestaña 'Dashboard'."); st.exception(e)

# --- PESTAÑA 2: OPERAR ---
with tabs[1]:
    # ... (código de la pestaña Operar sin cambios) ...
    pass

# --- PESTAÑA 3: EXPLORADOR ---
with tabs[2]:
    # ... (código de la pestaña Explorador sin cambios) ...
    pass

# --- PESTAÑA 4: NOTICIAS ---
with tabs[3]:
    # ... (código de la pestaña Noticias sin cambios) ...
    pass

# --- VENTANA FLOTANTE DE BALANCE (Se renderiza al final) ---
if total_market_value > 0:
    st.markdown(f"""
        <div class="floating-balance">
            <div class="label">VALOR TOTAL DEL PORTAFOLIO</div>
            <p class="value">${total_market_value:,.2f}</p>
        </div>
    """, unsafe_allow_html=True)