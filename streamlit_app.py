import pandas as pd
import altair as alt
import streamlit as st
from pymongo import MongoClient

# Configuração da página
st.set_page_config(page_title="Dashboard Financeiro", page_icon="💲", layout="wide")

# Título e botão de recarregar
col_titulo, col_botao = st.columns([4, 1])
with col_titulo:
    st.title("💲 Dashboard Financeiro via WhatsApp")
with col_botao:
    if st.button("🔄 Recarregar Dados"):
        st.cache_data.clear()
        st.experimental_rerun()

# Conexão com MongoDB
@st.cache_resource
def get_collection():
    uri = st.secrets["mongodb"]["uri"]
    db_name = st.secrets["mongodb"]["database"]
    col_name = st.secrets["mongodb"]["collection"]
    client = MongoClient(uri)
    db = client[db_name]
    return db[col_name]

# Carregar e tratar os dados
@st.cache_data(ttl=60)
def load_data():
    collection = get_collection()
    cursor = collection.find(
        {"message": {"$regex": r"^#F"}},
        {"_id": 0, "message": 1, "message_timestamp": 1}
    )
    rows = list(cursor)
    if not rows:
        return pd.DataFrame(columns=["message", "message_timestamp", "data", "descricao", "valor", "forma_pagamento"])

    df = pd.DataFrame(rows)
    df["message_timestamp"] = pd.to_datetime(df["message_timestamp"])
    df["data"] = df["message_timestamp"].dt.date

    # Parse das mensagens
    def parse_message(msg):
        partes = [p.strip() for p in msg.split("|")]
        if len(partes) >= 5:
            descricao = partes[1].lower()
            valor = partes[2].replace(",", ".")
            forma_pagamento = partes[4].capitalize()
            try:
                return descricao, float(valor), forma_pagamento
            except:
                return None, None, None
        return None, None, None

    df[["descricao", "valor", "forma_pagamento"]] = df["message"].apply(lambda x: pd.Series(parse_message(x)))
    df = df.dropna(subset=["valor", "forma_pagamento"])
    return df

# Carrega dados
df = load_data()

if df.empty:
    st.warning("Nenhum dado encontrado com o padrão '#F' no MongoDB.")
    st.stop()

# Sidebar - filtros
st.sidebar.header("Filtros")
min_data = df["data"].min()
max_data = df["data"].max()
data_inicio, data_fim = st.sidebar.date_input("Período", (min_data, max_data), min_value=min_data, max_value=max_data)
meta = st.sidebar.number_input("Valor da Meta (R$)", value=500.0, step=10.0)

# Aplica filtros
df = df[(df["data"].between(data_inicio, data_fim))]

# Cálculos para cards
total_gastos = df["valor"].sum()
total_credito = df[df["forma_pagamento"] == "Credito"]["valor"].sum()
total_debito = df[df["forma_pagamento"] == "Debito"]["valor"].sum()
total_alimentacao = df[df["descricao"].str.contains("alimenta", case=False)]["valor"].sum()

# Layout dos cards
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("💰 Total de Gastos", f"R$ {total_gastos:.2f}")
col2.metric("💳 Crédito", f"R$ {total_credito:.2f}")
col3.metric("💸 Débito", f"R$ {total_debito:.2f}")
col4.metric("🍔 Alimentação", f"R$ {total_alimentacao:.2f}")
col5.metric("🎯 Meta", f"R$ {meta:.2f}")

# Remove alimentação
df_sem_alimentacao = df[~df["descricao"].str.contains("alimenta", case=False)]

# Gráfico de Gastos Diários
st.subheader("📊 Gastos Diários (sem alimentação)")
df_diario = df_sem_alimentacao.groupby("data")["valor"].sum().reset_index()

chart_diario = (
    alt.Chart(df_diario)
    .mark_bar(size=25, color="#4C78A8")
    .encode(
        x=alt.X("data:T", title="Data"),
        y=alt.Y("valor:Q", title="Total Gasto (R$)"),
        tooltip=["data:T", "valor:Q"]
    )
    + alt.Chart(pd.DataFrame({"meta": [meta]})).mark_rule(color="red").encode(y='meta:Q')
).properties(height=350)

st.altair_chart(chart_diario, use_container_width=True)

# Gráfico Acumulado
st.subheader("📈 Acumulado Diário (sem alimentação)")
df_diario["acumulado"] = df_diario["valor"].cumsum()

chart_acumulado = (
    alt.Chart(df_diario)
    .mark_line(point=True, color="#F58518")
    .encode(
        x=alt.X("data:T", title="Data"),
        y=alt.Y("acumulado:Q", title="Gasto Acumulado (R$)"),
        tooltip=["data:T", "acumulado:Q"]
    )
    + alt.Chart(pd.DataFrame({"meta": [meta]})).mark_rule(color="red").encode(y='meta:Q')
).properties(height=350)

st.altair_chart(chart_acumulado, use_container_width=True)

# Tabela
st.subheader("📋 Tabela de Gastos")
st.dataframe(df[["data", "descricao", "valor", "forma_pagamento"]].sort_values("data"), use_container_width=True)
