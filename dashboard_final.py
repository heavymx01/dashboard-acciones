import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime
import os
import requests

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard de Portafolio Pro", page_icon="📈", layout="wide")

# --- TÍTULO ---
st.title("📈 Dashboard de Portafolio Profesional")
st.markdown(f"Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} (CST)")


# --- FUNCIONES AUXILIARES ---

@st.cache_data
def cargar_transacciones():
    """Carga las transacciones desde transacciones.csv, parseando las fechas."""
    if os.path.exists("transacciones.csv"):
        return pd.read_csv("transacciones.csv", parse_dates=['Fecha'])
    return pd.DataFrame(columns=["Tipo", "Ticker", "Cantidad", "Precio", "Fecha"])

def guardar_transacciones(df):
    """Guarda el DataFrame de transacciones en un archivo CSV."""
    df.to_csv("transacciones.csv", index=False)

@st.cache_data
def cargar_lista_tickers_gbm():
    """Carga la lista de tickers desde el archivo local tickers_gbm.csv."""
    archivo_local = "tickers_gbm.csv"
    if not os.path.exists(archivo_local):
        st.error(f"Error: No se encontró el archivo '{archivo_local}'. Por favor, créalo con las columnas 'Ticker,Name,Market'.")
        return None
    try:
        df = pd.read_csv(archivo_local)
        df['Display'] = df['Name'] + " (" + df['Ticker'] + ") - " + df['Market']
        return df
    except Exception as e:
        st.error(f"Error al leer {archivo_local}: {e}")
        return None

# --- INICIALIZACIÓN ---
if 'transactions' not in st.session_state:
    st.session_state.transactions = cargar_transacciones()

lista_tickers_df = cargar_lista_tickers_gbm()


# --- BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    st.header("Registrar Movimiento")
    # Este es el ÚNICO formulario con la key "transaction_form"
    with st.form("transaction_form", clear_on_submit=True):
        transaction_type = st.selectbox("Tipo de Movimiento", ["Compra", "Venta", "Dividendo"])
        ticker_seleccionado = None
        if lista_tickers_df is not None:
            opcion = st.selectbox("Buscar Acción (BMV/SIC)", options=lista_tickers_df['Display'], index=None, placeholder="Escribe para buscar...")
            if opcion:
                ticker_seleccionado = opcion.split('(')[1].split(')')[0]
        else:
            ticker_seleccionado = st.text_input("Ticker").upper()

        if transaction_type in ["Compra", "Venta"]:
            quantity = st.number_input("Cantidad", min_value=0.0001, format="%.4f")
            price = st.number_input("Precio", min_value=0.01, format="%.4f")
        else: # Dividendo
            quantity = 0
            price = st.number_input("Monto Total Dividendo", min_value=0.01, format="%.2f")

        date = st.date_input("Fecha", datetime.now())
        submitted = st.form_submit_button("Agregar Movimiento")

        if submitted:
            if ticker_seleccionado:
                new_transaction = pd.DataFrame([{"Tipo": transaction_type, "Ticker": ticker_seleccionado, "Cantidad": quantity, "Precio": price, "Fecha": pd.to_datetime(date)}])
                st.session_state.transactions = pd.concat([st.session_state.transactions, new_transaction], ignore_index=True)
                st.session_state.transactions['Fecha'] = pd.to_datetime(st.session_state.transactions['Fecha'])
                guardar_transacciones(st.session_state.transactions)
                st.success("¡Movimiento agregado!")
                st.rerun()
            else:
                st.error("Por favor, selecciona un ticker.")

    st.header("Gestionar Historial")
    if not st.session_state.transactions.empty:
        with st.expander("Ver y Eliminar Transacciones"):
            transactions_to_delete = []
            for idx in reversed(st.session_state.transactions.index):
                trans = st.session_state.transactions.loc[idx]
                col1, col2 = st.columns([1, 10])
                with col1:
                    if st.checkbox("", key=f"del_{idx}"):
                        transactions_to_delete.append(idx)
                with col2:
                    st.write(f"{trans['Fecha'].strftime('%Y-%m-%d')}: {trans['Tipo']} {trans['Ticker']} - Cant: {trans['Cantidad']:.2f}, Precio: ${trans['Precio']:,.2f}")
            
            if st.button("Eliminar Seleccionadas", type="primary"):
                if transactions_to_delete:
                    st.session_state.transactions = st.session_state.transactions.drop(transactions_to_delete).reset_index(drop=True)
                    guardar_transacciones(st.session_state.transactions)
                    st.success("Transacciones eliminadas.")
                    st.rerun()
                else:
                    st.warning("No has seleccionado ninguna transacción para eliminar.")


# --- PESTAÑAS DEL DASHBOARD PRINCIPAL ---
tab1, tab2, tab3 = st.tabs(["📊 Mi Portafolio", "📈 Rendimiento Histórico", "🔍 Explorador de Acciones"])

with tab1:
    st.subheader("Composición Actual del Portafolio")
    if not st.session_state.transactions.empty:
        df_trades = st.session_state.transactions[st.session_state.transactions['Tipo'].isin(['Compra', 'Venta'])]
        df_dividends = st.session_state.transactions[st.session_state.transactions['Tipo'] == 'Dividendo']
        total_dividends = df_dividends['Precio'].sum()

        portfolio = {}
        for ticker in df_trades['Ticker'].unique():
            df_ticker = df_trades[df_trades['Ticker'] == ticker]
            compras = df_ticker[df_ticker['Tipo'] == 'Compra']
            ventas = df_ticker[df_ticker['Tipo'] == 'Venta']
            cantidad_total = compras['Cantidad'].sum() - ventas['Cantidad'].sum()

            if cantidad_total > 0.0001:
                costo_total_compras = (compras['Cantidad'] * compras['Precio']).sum()
                costo_promedio = costo_total_compras / compras['Cantidad'].sum()
                costo_actual_ponderado = cantidad_total * costo_promedio
                portfolio[ticker] = {'Cantidad': cantidad_total, 'Costo Total': costo_actual_ponderado}
        
        if portfolio:
            portfolio_df = pd.DataFrame.from_dict(portfolio, orient='index').reset_index().rename(columns={'index': 'Ticker'})
            tickers_list = portfolio_df['Ticker'].tolist()
            
            try:
                data = yf.download(tickers_list, period="1d", progress=False)
                if not data.empty and 'Close' in data:
                    current_prices = data['Close'].iloc[-1] if isinstance(data['Close'], pd.Series) else data['Close'].tail(1).T.iloc[:,0]
                    portfolio_df['Precio Actual'] = portfolio_df['Ticker'].map(current_prices).fillna(0)
                    portfolio_df['Valor de Mercado'] = portfolio_df['Cantidad'] * portfolio_df['Precio Actual']
                    portfolio_df['Ganancia/Pérdida'] = portfolio_df['Valor de Mercado'] - portfolio_df['Costo Total']

                    total_market_value = portfolio_df['Valor de Mercado'].sum()
                    total_cost_basis = portfolio_df['Costo Total'].sum()
                    
                    st.metric("Valor Total del Portafolio", f"${total_market_value:,.2f}")
                    st.dataframe(portfolio_df)
                    fig_pie = px.pie(portfolio_df, values='Valor de Mercado', names='Ticker', title='Distribución del Portafolio')
                    st.plotly_chart(fig_pie, use_container_width=True)
            except Exception as e:
                st.error(f"No se pudieron obtener los datos de mercado: {e}")
        else:
            st.info("Tu portafolio está vacío. Agrega una compra para comenzar.")
    else:
        st.info("Bienvenido. Agrega tu primera transacción desde la barra lateral.")

with tab2:
    st.subheader("Rendimiento Histórico del Portafolio")
    st.info("El gráfico de rendimiento histórico requiere una lógica compleja y consume muchos recursos. Se implementará en una futura versión mejorada.")

with tab3:
    st.subheader("Explorador de Acciones e Información")
    ticker_a_explorar = None
    if lista_tickers_df is not None:
        opcion_exp = st.selectbox("Selecciona una acción para explorar", options=lista_tickers_df['Display'], index=None, placeholder="Busca por nombre o ticker...")
        if opcion_exp:
            ticker_a_explorar = opcion_exp.split('(')[1].split(')')[0]
    else:
        ticker_a_explorar = st.text_input("Ingresa un Ticker para Explorar").upper()

    if ticker_a_explorar:
        try:
            stock = yf.Ticker(ticker_a_explorar)
            info = stock.info
            st.write("---")
            
            st.header(f"{info.get('longName', ticker_a_explorar)} ({info.get('symbol', '')})")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Precio Actual", f"${info.get('currentPrice', info.get('previousClose', 0)):,.2f}")
                st.write(f"**Sector:** {info.get('sector', 'N/A')}")
            with col2:
                st.metric("Máximo del Día", f"${info.get('dayHigh', 0):,.2f}")
                st.write(f"**Industria:** {info.get('industry', 'N/A')}")
            with col3:
                st.metric("Mínimo del Día", f"${info.get('dayLow', 0):,.2f}")
                if info.get('website'):
                    st.write(f"**Sitio Web:** [{info.get('website')}]({info.get('website')})")

            with st.expander("Resumen del Negocio"):
                st.write(info.get('longBusinessSummary', 'No hay resumen disponible.'))
            
            st.subheader("Noticias Recientes")
            news = stock.news
            if news:
                for item in news[:8]:
                    st.markdown(f"**[{item['title']}]({item['link']})**")
                    st.write(f"*{item['publisher']}* - {datetime.fromtimestamp(item['providerPublishTime']).strftime('%Y-%m-%d')}")
                    st.write("---")
            else:
                st.write("No se encontraron noticias recientes.")
        except Exception as e:
            st.error(f"No se pudo obtener la información para {ticker_a_explorar}. Verifica el ticker o tu conexión.")