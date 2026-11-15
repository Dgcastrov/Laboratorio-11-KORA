import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="KORA | Conociendo a nuestros clientes", layout="wide")
st.title("KORA | Conociendo a nuestros clientes")
st.caption("Decisión: ¿en qué canal probar una campaña para motivar una segunda compra? "
           "· Usuario: Gerente de Marketing · Corte: 31/10/2026 · Ingresos en COP")

FECHA_CORTE = pd.Timestamp("2026-10-31") 
SIN_COMPRA = "Sin compra"
ORDEN_SEGMENTOS = [SIN_COMPRA, "Primerizos", "En desarrollo", "Fieles", "En pausa"]


def segmento(f):
    """Reglas de negocio de la Sesión 14 (umbrales = hipótesis operativas)."""
    if f.n_pedidos == 0: return "Sin compra"
    if f.dias_sin_compra > 90: return "En pausa"
    if f.n_pedidos >= 3: return "Fieles"
    if f.n_pedidos == 1: return "Primerizos"
    return "En desarrollo"


@st.cache_data
def cargar_datos(ruta_clientes="KORA_clientes.csv", ruta_pedidos="KORA_pedidos.csv"):
    clientes = pd.read_csv(ruta_clientes, parse_dates=["fecha_registro"])
    pedidos = pd.read_csv(ruta_pedidos, parse_dates=["fecha_pedido"])

    # Controles de integridad (Sesión 14, paso 1)
    assert clientes["id_cliente"].is_unique
    assert pedidos["id_pedido"].is_unique
    assert pedidos["id_cliente"].isin(clientes["id_cliente"]).all()

    # Se agrega a nivel cliente ANTES del merge para no duplicar clientes (paso 2)
    resumen = (pedidos.groupby("id_cliente")
               .agg(n_pedidos=("id_pedido", "nunique"),
                    ingreso_total=("ingreso_neto_cop", "sum"),
                    ultima_compra=("fecha_pedido", "max"))
               .reset_index())
    perfil = clientes.merge(resumen, how="left", on="id_cliente", validate="one_to_one")

    # Variables derivadas (paso 3): quien no compró queda con 0 pedidos
    perfil["n_pedidos"] = perfil["n_pedidos"].fillna(0).astype(int)
    perfil["ingreso_total"] = perfil["ingreso_total"].fillna(0)
    perfil["dias_sin_compra"] = (FECHA_CORTE - perfil["ultima_compra"]).dt.days

    perfil["segmento"] = perfil.apply(segmento, axis=1)   # paso 4
    return perfil


def filtrar(df, ciudades, canales, segmentos, preferencias):
    """Aplica los cuatro filtros a la vez. Una lista vacía deja la selección sin clientes."""
    return df[
        df["ciudad"].isin(ciudades)
        & df["canal_adquisicion"].isin(canales)
        & df["segmento"].isin(segmentos)
        & df["preferencia_declarada"].isin(preferencias)
    ]


def metricas_recompra(df):
    """Comprador = cliente con al menos 1 pedido. Todo se calcula sobre la selección recibida."""
    compradores = df[df["n_pedidos"] >= 1]
    n = len(compradores)
    una = int((compradores["n_pedidos"] == 1).sum())
    dos_o_mas = int((compradores["n_pedidos"] >= 2).sum())
    return {
        "clientes": len(df),
        "compradores": n,
        "una_compra": una,
        "pct_una_compra": una / n * 100 if n else None,
        "tasa_recompra": dos_o_mas / n * 100 if n else None,
    }


def tabla_canales(df):
    """Por canal: compradores, con 2+ pedidos, con exactamente 1 pedido y tasa de recompra (%)."""
    compradores = df[df["n_pedidos"] >= 1]
    t = (compradores
         .assign(recompra=compradores["n_pedidos"] >= 2,
                 una=compradores["n_pedidos"] == 1)
         .groupby("canal_adquisicion", as_index=False)
         .agg(compradores=("id_cliente", "count"),
              recompradores=("recompra", "sum"),
              una_compra=("una", "sum")))
    t["tasa_recompra"] = (t["recompradores"] / t["compradores"] * 100).round(1)
    return t


def grafico_tasa(t):
    """Barras: % de compradores con 2+ pedidos por canal, con n en la etiqueta y en el hover."""
    t = t.sort_values("tasa_recompra", ascending=False).copy()
    t["etiqueta"] = (t["tasa_recompra"].astype(str) + " % (n = "
                     + t["compradores"].astype(str) + ")")
    tope = max(10, min(100, t["tasa_recompra"].max() * 1.3))
    fig = px.bar(
        t, x="canal_adquisicion", y="tasa_recompra", text="etiqueta",
        category_orders={"canal_adquisicion": t["canal_adquisicion"].tolist()},
        hover_data={"compradores": True, "recompradores": True, "tasa_recompra": ":.1f"},
        labels={"canal_adquisicion": "Canal de adquisición",
                "tasa_recompra": "Compradores con 2+ pedidos (%)",
                "compradores": "Compradores (n)",
                "recompradores": "Con 2+ pedidos"},
        title="Tasa de recompra por canal (n = compradores del canal)",
    )
    fig.update_traces(textposition="outside")
    fig.update_yaxes(range=[0, tope])
    return fig


def grafico_una_compra(t):
    """Barras ordenadas: clientes con exactamente 1 pedido por canal."""
    t = t.sort_values("una_compra", ascending=False).copy()
    fig = px.bar(
        t, x="canal_adquisicion", y="una_compra", text="una_compra",
        category_orders={"canal_adquisicion": t["canal_adquisicion"].tolist()},
        hover_data={"compradores": True, "tasa_recompra": ":.1f", "una_compra": True},
        labels={"canal_adquisicion": "Canal de adquisición",
                "una_compra": "Clientes con exactamente 1 pedido",
                "compradores": "Compradores (n)",
                "tasa_recompra": "Tasa de recompra (%)"},
        title="Clientes con exactamente una compra, por canal",
    )
    fig.update_traces(textposition="outside")
    return fig


df = cargar_datos()

# Variables de apoyo para comprobar los filtros
ciudades = sorted(df["ciudad"].unique().tolist())
canales = sorted(df["canal_adquisicion"].unique().tolist())
segmentos = ORDEN_SEGMENTOS
preferencias = sorted(df["preferencia_declarada"].unique().tolist())

# Filtros
st.sidebar.header("Filtros")
filtro_ciudad = st.sidebar.multiselect(
    "Ciudad", options=sorted(df["ciudad"].unique().tolist()),
    default=sorted(df["ciudad"].unique().tolist()))
filtro_canal = st.sidebar.multiselect(
    "Canal de adquisición", options=sorted(df["canal_adquisicion"].unique().tolist()),
    default=sorted(df["canal_adquisicion"].unique().tolist()))
filtro_segmento = st.sidebar.multiselect(
    "Segmento", options=ORDEN_SEGMENTOS, default=ORDEN_SEGMENTOS)
filtro_preferencia = st.sidebar.multiselect(
    "Preferencia declarada", options=sorted(df["preferencia_declarada"].unique().tolist()),
    default=sorted(df["preferencia_declarada"].unique().tolist()))

df_sel = filtrar(df, filtro_ciudad, filtro_canal, filtro_segmento, filtro_preferencia)
m = metricas_recompra(df_sel)
#Métricas
st.subheader("Segunda compra: ¿dónde probar una campaña?")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Clientes en la selección", f"{m['clientes']:,}")
c2.metric("Compradores (1+ pedidos)", f"{m['compradores']:,}")
c3.metric("Tasa de recompra (2+ pedidos)",
          f"{m['tasa_recompra']:.1f} %" if m["tasa_recompra"] is not None else "—")
c4.metric("Clientes con exactamente 1 compra", f"{m['una_compra']:,}")
c5.metric("% de una sola compra entre compradores",
          f"{m['pct_una_compra']:.1f} %" if m["pct_una_compra"] is not None else "—")
#Gráficos
if m["compradores"] == 0:
    st.warning("No hay compradores con los filtros seleccionados. "
               "Amplíen la ciudad, el canal, el segmento o la preferencia.")
else:
    t = tabla_canales(df_sel)
    st.plotly_chart(grafico_tasa(t), width="stretch")
    st.plotly_chart(grafico_una_compra(t), width="stretch")
    st.caption("Comprador = cliente con al menos un pedido. Tasa de recompra = compradores "
               "con 2 o más pedidos / compradores del canal. Los clientes registrados hasta el "
               "24/09/2026 han tenido pocas semanas para volver a comprar; los canales no "
               "prueban causalidad (puede reflejar el tipo de cliente).")



st.header("1. ¿Por qué no basta la tasa de recompra?")

st.write(
    "La tasa de recompra indica el porcentaje de compradores "
    "que realizaron dos o más pedidos. Sin embargo, no es "
    "suficiente para elegir un canal porque no muestra cuántos "
    "clientes podrían recibir una campaña de segunda compra. "
    "Un canal puede tener una tasa baja, pero pocos clientes, "
    "mientras que otro puede tener una tasa mayor y muchos "
    "clientes con exactamente un pedido. Por eso analizamos "
    "tanto la tasa como el volumen de clientes con una compra."
)

st.latex(
    r"\text{Tasa de recompra} = "
    r"\frac{\text{Compradores con 2 o más pedidos}}"
    r"{\text{Total de compradores}}\times 100"
)

st.write(
    "Los clientes con exactamente una compra son aquellos "
    "que realizaron un solo pedido hasta la fecha de corte. "
    "Representan posibles participantes de una campaña "
    "para motivar una segunda compra."
)


# --------------------------------------------------
# PUNTO 2. METRICAS
# --------------------------------------------------

st.header("2. Métricas de segunda compra")

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("Clientes seleccionados", f"{m['clientes']:,}")

c2.metric("Compradores", f"{m['compradores']:,}")

c3.metric(
    "Tasa de recompra",
    f"{m['tasa_recompra']:.1f}%"
    if m["tasa_recompra"] is not None else "—"
)

c4.metric(
    "Clientes con 1 compra",
    f"{m['una_compra']:,}"
)

c5.metric(
    "% con 1 compra",
    f"{m['pct_una_compra']:.1f}%"
    if m["pct_una_compra"] is not None else "—"
)

st.caption(
    "Las métricas se calculan sobre los clientes que cumplen "
    "los cuatro filtros. Los porcentajes usan únicamente "
    "compradores con al menos un pedido."
)


# --------------------------------------------------
# PUNTOS 3 Y 4. VISUALIZACIONES
# --------------------------------------------------

st.header("3. Comparación de la tasa de recompra")

if m["compradores"] == 0:
    st.warning(
        "No hay compradores con los filtros seleccionados. "
        "Modifica los filtros para visualizar los resultados."
    )

else:
    t = tabla_canales(df_sel)
    
    st.plotly_chart(
    grafico_tasa(t),
    use_container_width=True,
    key="grafico_tasa_recompra")

   

    st.write(
        "**Justificación del gráfico:** Se utiliza un gráfico "
        "de barras porque permite comparar fácilmente el "
        "porcentaje de recompra entre canales. Además, "
        "cada barra muestra el número de compradores que "
        "compone la tasa, evitando interpretar porcentajes "
        "sin considerar el tamaño del grupo."
    )

    st.header("4. Clientes con exactamente una compra")

    st.plotly_chart(
        grafico_una_compra(t),
        use_container_width=True
    )

    st.write(
        "**Justificación del gráfico:** Las barras están "
        "ordenadas de mayor a menor para identificar "
        "rápidamente los canales con más clientes "
        "que todavía no realizan una segunda compra."
    )

    mayor_volumen = t.sort_values(
        "una_compra", ascending=False
    ).iloc[0]

    menor_tasa = t.sort_values(
        "tasa_recompra", ascending=True
    ).iloc[0]

    st.subheader("¿Coinciden el mayor volumen y la menor tasa?")

    if mayor_volumen["canal_adquisicion"] == menor_tasa["canal_adquisicion"]:
        st.write(
            f"En esta selección sí coinciden. El canal "
            f"**{mayor_volumen['canal_adquisicion']}** tiene "
            f"el mayor número de clientes con una compra "
            f"({mayor_volumen['una_compra']:,}) y también "
            f"la menor tasa de recompra "
            f"({mayor_volumen['tasa_recompra']:.1f}%). "
            f"Sin embargo, esta coincidencia no es una regla general."
        )
    else:
        st.write(
            f"No coinciden. El canal con mayor volumen es "
            f"**{mayor_volumen['canal_adquisicion']}**, "
            f"con {mayor_volumen['una_compra']:,} clientes "
            f"de una compra. En cambio, la menor tasa "
            f"corresponde a "
            f"**{menor_tasa['canal_adquisicion']}**, "
            f"con {menor_tasa['tasa_recompra']:.1f}%. "
            f"Esto demuestra que el volumen y la tasa "
            f"representan dimensiones diferentes."
        )

    st.subheader("Tabla de resultados por canal")
    st.dataframe(t, use_container_width=True, hide_index=True)


    # --------------------------------------------------
    # PUNTO 6. RECOMENDACION
    # --------------------------------------------------

    st.header("6. Recomendación para el piloto")

    # Criterio: priorizar el mayor grupo elegible
    # y usar la tasa para contextualizar la decisión.
    candidato = t.sort_values(
        ["una_compra", "tasa_recompra"],
        ascending=[False, True]
    ).iloc[0]

    canal = candidato["canal_adquisicion"]
    cantidad = int(candidato["una_compra"])
    tasa = candidato["tasa_recompra"]

    st.success(
        f"Recomendamos iniciar un piloto de segunda compra "
        f"en el canal **{canal}**, porque concentra "
        f"**{cantidad:,} clientes con exactamente un pedido** "
        f"y presenta una **tasa de recompra de {tasa:.1f}%**. "
        f"Esto permite probar la campaña sobre un grupo "
        f"amplio de compradores potenciales. "
        f"Una limitación es que algunos clientes han tenido "
        f"poco tiempo para realizar otra compra y las "
        f"diferencias entre canales no demuestran causalidad. "
        f"Para evaluar el piloto mediríamos la tasa de "
        f"segunda compra de los clientes que reciban "
        f"la campaña frente a un grupo de control."
    )


# --------------------------------------------------
# PUNTO 5. COMPROBACION DE FILTROS
# --------------------------------------------------

st.header("5. Comprobación de filtros")

st.write(
    "Los filtros de ciudad, canal, segmento y preferencia "
    "declarada afectan simultáneamente las métricas y "
    "los dos gráficos."
)

# Dos selecciones de prueba usando valores existentes
if ciudades and canales and preferencias:

    prueba1 = filtrar(
        df,
        [ciudades[0]],
        canales,
        segmentos,
        preferencias
    )

    prueba2 = filtrar(
        df,
        ciudades,
        [canales[0]],
        segmentos,
        [preferencias[0]]
    )

    resultados = []

    for nombre, datos in [
        ("Prueba 1: primera ciudad", prueba1),
        ("Prueba 2: primer canal y preferencia", prueba2),
        ("Selección actual del usuario", df_sel)
    ]:
        valores = metricas_recompra(datos)

        resultados.append({
            "Selección": nombre,
            "Clientes": valores["clientes"],
            "Compradores": valores["compradores"],
            "Una compra": valores["una_compra"],
            "Tasa de recompra (%)": valores["tasa_recompra"]
        })

    st.dataframe(
        pd.DataFrame(resultados),
        use_container_width=True,
        hide_index=True
    )

# Prueba de selección vacía
vacio = filtrar(df, [], canales, segmentos, preferencias)
m_vacio = metricas_recompra(vacio)

if m_vacio["compradores"] == 0:
    st.info(
        "Prueba sin compradores: correcta. "
        "La selección vacía produce 0 compradores, "
        "0 clientes con una compra y porcentajes no definidos. "
        "No se intenta dividir entre cero."
    )

st.caption(
    "Fecha de corte: 31/10/2026. "
    "Las tasas son descriptivas y no prueban "
    "que un canal cause una mayor o menor recompra."
)
