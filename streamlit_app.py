import pandas as pd
import altair as alt
import streamlit as st
from pymongo import MongoClient

# Configuração da página
st.set_page_config(page_title="Dashboard Financeiro", page_icon="💲")
st.title("💲 Dashboard Financeiro via WhatsApp")

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

    # DEBUG 1: Total de documentos
    # total_docs = collection.count_documents({})
    # st.write("📄 Total de documentos no MongoDB:", total_docs)

    # DEBUG 2: Documentos que começam com #F
    cursor = collection.find(
        {"message": {"$regex": r"^#F"}},
        {"_id": 0, "message": 1, "message_timestamp": 1}
    )

    rows = list(cursor)
    # st.write("🔍 Quantos com #F:", len(rows))
    # if rows:
    #     continue
    #     # st.write("📝 Exemplo de mensagens:", rows[:3])
    # else:
    #     st.info("⚠️ Nenhuma mensagem encontrada com prefixo '#F'.")

    # if not rows:
    #     return pd.DataFrame(columns=["message", "message_timestamp", "data", "descricao", "valor", "forma_pagamento"])

    df = pd.DataFrame(rows)
    df["message_timestamp"] = pd.to_datetime(df["message_timestamp"])
    df["data"] = df["message_timestamp"].dt.date

    # Parse das mensagens
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
    return df

# Carrega os dados
df = load_data()

if df.empty:
    st.warning("Nenhum dado encontrado com o padrão '#F' no MongoDB.")
    st.stop()

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

# Agrupa por dia
df_grouped = df_filtrado.groupby("data")["valor"].sum().reset_index()

# Tabela detalhada
st.subheader("📋 Tabela de Gastos Filtrados")
st.dataframe(df_filtrado[["data", "descricao", "valor", "forma_pagamento"]], use_container_width=True)

# Gráfico de barras diário
st.subheader("📊 Gastos Diários")
chart = (
    alt.Chart(df_grouped)
    .mark_bar()
    .encode(
        x=alt.X("data:T", title="Data"),
        y=alt.Y("valor:Q", title="Total Gasto (R$)"),
        tooltip=["data:T", "valor:Q"]
    )
    .properties(height=400)
)
st.altair_chart(chart, use_container_width=True)
