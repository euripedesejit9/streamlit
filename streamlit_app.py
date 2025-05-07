import pandas as pd
import altair as alt
import streamlit as st
from pymongo import MongoClient
import unicodedata

# Configuração da página
st.set_page_config(page_title="Dashboard Financeiro", page_icon="💲")
st.title("💲 Dashboard Financeiro via WhatsApp")

# 👉 Função para normalizar texto (remover acentos e colocar lowercase)
def normalizar_texto(texto):
    if not isinstance(texto, str):
        return ""
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8')
    return texto.lower().strip()

# 🔁 Botão para recarregar dados
col_botao, _ = st.columns([1, 5])
with col_botao:
    if st.button("🔄 Recarregar Dados"):
        st.cache_data.clear()

# Conexão com MongoDB usando secrets
@st.cache_resource
def get_collection():
    uri = st.secrets["mongodb"]["uri"]
    db_name = st.secrets["mongodb"]["database"]
    col_name = st.secrets["mongodb"]["collection"]

    client = MongoClient(uri)
    db = client[db_name]
    return db[col_name]

# Carregar e tratar os dados
@st.cache_data
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

    def parse_message(msg):
        partes = [p.strip() for p in msg.split("|")]
        if len(partes) >= 5:
            descricao = partes[1]
            valor = partes[2].replace(",", ".")
            forma_pagamento = partes[4]
            try:
                return descricao, float(valor), forma_pagamento
            except:
                return None, None, None
        return None, None, None

    df[["descricao", "valor", "forma_pagamento"]] = df["message"].apply(lambda x: pd.Series(parse_message(x)))
    df = df.dropna(subset=["valor", "forma_pagamento"])

    # Normaliza forma de pagamento
    df["forma_pagamento"] = df["forma_pagamento"].apply(normalizar_texto)
    df["descricao"] = df["descricao"].astype(str)
    return df

# Carrega os dados
df = load_data()

if df.empty:
    st.warning("Nenhum dado encontrado com o padrão '#F' no MongoDB.")
    st.stop()

# 🎯 Metas e cálculos
meta_valor = 3600  # Altere conforme desejar

total_gastos = df["valor"].sum()
total_credito = df[df["forma_pagamento"] == "credito"]["valor"].sum()
total_debito = df[df["forma_pagamento"] == "debito"]["valor"].sum()
total_alimentacao = df[df["descricao"].str.contains("alimenta", case=False)]["valor"].sum()

# 🧮 Cards resumo
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("💰 Total Gasto", f"R$ {total_gastos:,.2f}")
col2.metric("📇 Crédito", f"R$ {total_credito:,.2f}")
col3.metric("🏦 Débito", f"R$ {total_debito:,.2f}")
col4.metric("🍔 Alimentação", f"R$ {total_alimentacao:,.2f}")
col5.metric("🎯 Meta", f"R$ {meta_valor:,.2f}")

# 🔎 Filtros (usado apenas para o DataFrame)
st.sidebar.header("Filtros")

min_data = df["data"].min()
max_data = df["data"].max()
data_inicio, data_fim = st.sidebar.date_input("Período", (min_data, max_data), min_value=min_data, max_value=max_data)

formas = sorted(df["forma_pagamento"].unique())
formas_selecionadas = st.sidebar.multiselect("Forma de Pagamento", formas, default=formas)

# Aplica filtros ao DataFrame principal
df_filtrado = df[
    (df["data"].between(data_inicio, data_fim)) &
    (df["forma_pagamento"].isin(formas_selecionadas))
]

# Remove alimentação para os gráficos
df_sem_alimentacao = df_filtrado[~df_filtrado["descricao"].str.contains("alimenta", case=False)]

# 📊 Gráfico de gastos diários
st.subheader("📊 Gastos Diários (sem alimentação)")
df_grouped = df_sem_alimentacao.groupby("data")["valor"].sum().reset_index()

chart_diario = (
    alt.Chart(df_grouped)
    .mark_bar(size=25)
    .encode(
        x=alt.X("data:T", title="Data"),
        y=alt.Y("valor:Q", title="Total Gasto (R$)"),
        tooltip=["data:T", "valor:Q"]
    )
    .properties(height=300)
)

# Linha da meta
linha_meta = alt.Chart(pd.DataFrame({'meta': [meta_valor]})).mark_rule(color='red').encode(y='meta')
st.altair_chart(chart_diario + linha_meta, use_container_width=True)

# 📈 Gráfico de acumulado
st.subheader("📈 Acumulado até o dia atual (sem alimentação)")
df_grouped["acumulado"] = df_grouped["valor"].cumsum()
chart_acumulado = (
    alt.Chart(df_grouped)
    .mark_line(point=True)
    .encode(
        x=alt.X("data:T", title="Data"),
        y=alt.Y("acumulado:Q", title="Acumulado (R$)"),
        tooltip=["data:T", "acumulado:Q"]
    )
    .properties(height=300)
)
st.altair_chart(chart_acumulado, use_container_width=True)

# 📋 Tabela detalhada abaixo dos gráficos
st.subheader("📋 Tabela Detalhada (dados filtrados)")
st.dataframe(df_filtrado[["data", "descricao", "valor", "forma_pagamento"]], use_container_width=True)
