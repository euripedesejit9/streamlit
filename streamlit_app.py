import pandas as pd
import altair as alt
import streamlit as st
from pymongo import MongoClient
import unicodedata

# Configuração da página
st.set_page_config(page_title="Dashboard Financeiro", page_icon="💲", layout="wide")
st.title("💲 Dashboard Financeiro via WhatsApp")

# Botão para recarregar os dados
col_botao = st.columns([1])[0]
if col_botao.button("🔄 Recarregar Dados"):
    st.cache_data.clear()
    st.rerun()

# Conexão com MongoDB
@st.cache_resource
def get_collection():
    uri = st.secrets["mongodb"]["uri"]
    db_name = st.secrets["mongodb"]["database"]
    col_name = st.secrets["mongodb"]["collection"]
    client = MongoClient(uri)
    db = client[db_name]
    return db[col_name]

# Carrega e trata os dados
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

    # Remove nulos
    df = df.dropna(subset=["valor", "forma_pagamento"])

    # Padroniza forma de pagamento removendo acentos e deixando minúsculo
    df["forma_pagamento"] = df["forma_pagamento"].apply(
        lambda x: unicodedata.normalize("NFKD", x).encode("ASCII", "ignore").decode("utf-8").capitalize()
    )

    return df

# Carrega os dados
df = load_data()

if df.empty:
    st.warning("Nenhum dado encontrado com o padrão '#F' no MongoDB.")
    st.stop()

# Calcula totais
total_gastos = df["valor"].sum()
total_credito = df[df["forma_pagamento"] == "Credito"]["valor"].sum()
total_debito = df[df["forma_pagamento"] == "Debito"]["valor"].sum()
total_alimentacao = df[df["forma_pagamento"] == "Alimentacao"]["valor"].sum()
meta_valor = 3600

# 🎯 Cards com métricas (2 linhas para evitar sobreposição)
col1, col2, col3 = st.columns([1, 1, 1])  # Ajuste para 3 colunas com larguras iguais
col1.metric("💰 Total Gasto", f"R$ {total_gastos:,.2f}")
col2.metric("📇 Crédito", f"R$ {total_credito:,.2f}")
col3.metric("🏦 Débito", f"R$ {total_debito:,.2f}")

col4, col5, col6 = st.columns([1, 1, 1])  # Ajuste para 2 colunas com larguras iguais
col4.metric("🍔 Alimentação", f"R$ {total_alimentacao:,.2f}")
col5.metric("🎯 Meta", f"R$ {meta_valor:,.2f}")

# 🎛 Filtros interativos
st.sidebar.header("Filtros")

# Filtro por data
min_data = df["data"].min()
max_data = df["data"].max()
data_inicio, data_fim = st.sidebar.date_input("Período", (min_data, max_data), min_value=min_data, max_value=max_data)

# Filtro por forma de pagamento
formas = sorted(df["forma_pagamento"].unique())
formas_selecionadas = st.sidebar.multiselect("Forma de Pagamento", formas, default=formas)

# Aplica filtros
df_filtrado = df[
    (df["data"].between(data_inicio, data_fim)) &
    (df["forma_pagamento"].isin(formas_selecionadas))
]

# Remove alimentação
df_sem_alimentacao = df_filtrado[~df_filtrado["descricao"].str.contains("alimenta", case=False, na=False)]

# 📊 Gráfico de gastos diários
st.subheader("📅 Gastos Diários (sem alimentação)")

# Agrupa os dados por data e soma os valores
df_grouped = df_sem_alimentacao.groupby("data")["valor"].sum().reset_index()

# Gráfico de barras de gastos diários
chart_diario = (
    alt.Chart(df_grouped)
    .mark_bar(size=20, color="green")  # Barras mais largas
    .encode(
        x=alt.X("data:T", title="Data"),
        y=alt.Y("valor:Q", title="Total Gasto (R$)"),
        tooltip=["data:T", "valor:Q"]
    )
    .properties(height=400)
)

st.altair_chart(chart_diario, use_container_width=True)

# 📊 Gráfico de Gasto Acumulado com Meta
st.subheader("📊 Gasto Acumulado (sem alimentação) com Meta")

# Calcula valor acumulado
df_grouped["valor_acumulado"] = df_grouped["valor"].cumsum()
df_grouped["meta"] = meta_valor  # meta para cada dia, para exibir como linha horizontal

# Gráfico de barras do acumulado
chart_acumulado_barras = (
    alt.Chart(df_grouped)
    .mark_bar(color="steelblue", size=20)
    .encode(
        x=alt.X("data:T", title="Data"),
        y=alt.Y("valor_acumulado:Q", title="Gasto Acumulado (R$)"),
        tooltip=["data:T", "valor_acumulado:Q"]
    )
)

# Define cor da linha de meta com base no valor final
cor_meta = "red" if df_grouped["valor_acumulado"].iloc[-1] > meta_valor else "green"

# Linha horizontal de meta
linha_meta = (
    alt.Chart(df_grouped)
    .mark_rule(strokeWidth=2, color=cor_meta)
    .encode(
        y="meta:Q"
    )
)

# Combina os dois gráficos
chart_final = (chart_acumulado_barras + linha_meta).properties(height=400)

# Exibe o gráfico
st.altair_chart(chart_final, use_container_width=True)



# 📋 Tabela de Gastos
st.subheader("📋 Tabela de Gastos")
st.dataframe(df_filtrado[["data", "descricao", "valor", "forma_pagamento"]], use_container_width=True)
