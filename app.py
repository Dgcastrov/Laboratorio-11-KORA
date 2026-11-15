
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(
    page_title="KORA | Conociendo a nuestros clientes",
    layout="wide"
)

st.title("KORA | Conociendo a nuestros clientes")
st.caption(
    "Decisión: ¿en qué canal probar una campaña para motivar una segunda compra? "
    "· Usuario: Gerente de Marketing · Corte: 31/10/2026 · Ingresos en COP"
)

FECHA_CORTE = pd.Timestamp("2026-10-31")
SIN_COMPRA = "Sin compra"
ORDEN_SEGMENTOS = [
    SIN_COMPRA, "Primerizos", "En desarrollo", "Fieles", "En pausa"
]


# ==================================================
# FUNCIONES ORIGINALES DE KORA
# ==================================================

def segmento(f):
    """Reglas de negocio de la Sesión 14."""
    if f.n_pedidos == 0:
        return "Sin compra"
    if f.dias_sin_compra > 90:
        return "En pausa"
    if f.n_pedidos >= 3:
        return "Fieles"
    if f.n_pedidos == 1:
        return "Primerizos"
    return "En desarrollo"


@st.cache_data
def cargar_datos(
    ruta_clientes="KORA_clientes.csv",
    ruta_pedidos="KORA_pedidos.csv"
):
    clientes = pd.read_csv(
        ruta_clientes, parse_dates=["fecha_registro"]
    )
    pedidos = pd.read_csv(
        ruta_pedidos, parse_dates=["fecha_pedido"]
    )

    # Controles de integridad
    assert clientes["id_cliente"].is_unique
    assert pedidos["id_pedido"].is_unique
    assert pedidos["id_cliente"].isin(clientes["id_cliente"]).all()

    # Agregar pedidos por cliente antes de unir
    resumen = (
        pedidos.groupby("id_cliente")
        .agg(
            n_pedidos=("id_pedido", "nunique"),
            ingreso_total=("ingreso_neto_cop", "sum"),
            ultima_compra=("fecha_pedido", "max")
        )
        .reset_index()
    )

    perfil = clientes.merge(
        resumen,
        how="left",
        on="id_cliente",
        validate="one_to_one"
    )

    perfil["n_pedidos"] = perfil["n_pedidos"].fillna(0).astype(int)
    perfil["ingreso_total"] = perfil["ingreso_total"].fillna(0)

    perfil["dias_sin_compra"] = (
        FECHA_CORTE - perfil["ultima_compra"]
    ).dt.days

    perfil["segmento"] = perfil.apply(segmento, axis=1)

    return perfil


def filtrar(df, ciudades, canales, segmentos, preferencias):
    """Aplica los cuatro filtros simultaneamente."""
    return df[
        df["ciudad"].isin(ciudades)
        & df["canal_adquisicion"].isin(canales)
        & df["segmento"].isin(segmentos)
        & df["preferencia_declarada"].isin(preferencias)
    ]


def metricas_recompra(df):
    """Calcula las metricas sobre los clientes filtrados."""
    compradores = df[df["n_pedidos"] >= 1]

    n = len(compradores)
    una = int((compradores["n_pedidos"] == 1).sum())
    dos_o_mas = int((compradores["n_pedidos"] >= 2).sum())

    return {
        "clientes": len(df),
        "compradores": n,
        "una_compra": una,
        "pct_una_compra": una / n * 100 if n else None,
        "tasa_recompra": dos_o_mas / n * 100 if n else None
    }


def tabla_canales(df):
    """Resume las compras por canal de adquisicion."""
    compradores = df[df["n_pedidos"] >= 1].copy()

    compradores["recompra"] = compradores["n_pedidos"] >= 2
    compradores["una"] = compradores["n_pedidos"] == 1

    t = (
        compradores.groupby("canal_adquisicion", as_index=False)
        .agg(
            compradores=("id_cliente", "nunique"),
            recompradores=("recompra", "sum"),
            una_compra=("una", "sum")
        )
    )

    t["tasa_recompra"] = (
        t["recompradores"] / t["compradores"] * 100
    ).round(1)

    return t


def grafico_tasa(t):
    """Grafico de tasa de recompra por canal."""
    t = t.sort_values(
        "tasa_recompra", ascending=False
    ).copy()

    t["etiqueta"] = (
        t["tasa_recompra"].astype(str)
        + " % (n = "
        + t["compradores"].astype(str)
        + ")"
    )

    tope = max(
        10, min(110, t["tasa_recompra"].max() * 1.3)
    )

    fig = px.bar(
        t,
        x="canal_adquisicion",
        y="tasa_recompra",
        text="etiqueta",
        category_orders={
            "canal_adquisicion": t["canal_adquisicion"].tolist()
        },
        hover_data={
            "compradores": True,
            "recompradores": True,
            "tasa_recompra": ":.1f"
        },
        labels={
            "canal_adquisicion": "Canal de adquisición",
            "tasa_recompra": "Compradores con 2+ pedidos (%)",
            "compradores": "Compradores (n)",
            "recompradores": "Con 2+ pedidos"
        },
        title="Tasa de recompra por canal (n = compradores del canal)"
    )

    fig.update_traces(textposition="outside")
    fig.update_yaxes(range=[0, tope])

    return fig


def grafico_una_compra(t):
    """Grafico ordenado de clientes con una compra."""
    t = t.sort_values(
        "una_compra", ascending=False
    ).copy()

    fig = px.bar(
        t,
        x="canal_adquisicion",
        y="una_compra",
        text="una_compra",
        category_orders={
            "canal_adquisicion": t["canal_adquisicion"].tolist()
        },
        hover_data={
            "compradores": True,
            "tasa_recompra": ":.1f",
            "una_compra": True
        },
        labels={
            "canal_adquisicion": "Canal de adquisición",
            "una_compra": "Clientes con exactamente 1 pedido",
            "compradores": "Compradores (n)",
            "tasa_recompra": "Tasa de recompra (%)"
        },
        title="Clientes con exactamente una compra, por canal"
    )

    fig.update_traces(textposition="outside")

    return fig


# ==================================================
# CARGA DE DATOS Y FILTROS ORIGINALES
# ==================================================

df = cargar_datos()

ciudades = sorted(df["ciudad"].dropna().unique().tolist())
canales = sorted(df["canal_adquisicion"].dropna().unique().tolist())
segmentos = ORDEN_SEGMENTOS
preferencias = sorted(
    df["preferencia_declarada"].dropna().unique().tolist()
)

st.sidebar.header("Filtros")

filtro_ciudad = st.sidebar.multiselect(
    "Ciudad",
    options=ciudades,
    default=ciudades
)

filtro_canal = st.sidebar.multiselect(
    "Canal de adquisición",
    options=canales,
    default=canales
)

filtro_segmento = st.sidebar.multiselect(
    "Segmento",
    options=segmentos,
    default=segmentos
)

filtro_preferencia = st.sidebar.multiselect(
    "Preferencia declarada",
    options=preferencias,
    default=preferencias
)

df_sel = filtrar(
    df,
    filtro_ciudad,
    filtro_canal,
    filtro_segmento,
    filtro_preferencia
)

m = metricas_recompra(df_sel)


# ==================================================
# PUNTO 1. JUSTIFICACION
# ==================================================

st.header("1. ¿Por qué no basta la tasa de recompra?")

st.write(
    "La tasa de recompra por sí sola no es suficiente para "
    "elegir el canal más adecuado porque únicamente muestra "
    "qué porcentaje de compradores realizó dos o más pedidos, "
    "pero no indica cuántos clientes podrían participar en "
    "una campaña. Un canal puede tener una tasa baja, pero "
    "pocos compradores, mientras que otro puede tener una "
    "tasa mayor y muchos clientes con una sola compra. "
    "Por eso debemos analizar ambas dimensiones."
)

st.latex(
    r"\text{Tasa de recompra} = "
    r"\frac{\text{Compradores con 2 o más pedidos}}"
    r"{\text{Total de compradores}}\times 100"
)

st.write(
    "El número de clientes con exactamente una compra mide "
    "cuántos compradores realizaron un único pedido hasta "
    "la fecha de corte. Estos clientes representan el grupo "
    "potencial para una campaña de segunda compra."
)


# ==================================================
# PUNTO 2. METRICAS ORIGINALES
# ==================================================

st.header("2. Métricas de segunda compra")

st.subheader("Segunda compra: ¿dónde probar una campaña?")

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric(
    "Clientes en la selección",
    f"{m['clientes']:,}"
)

c2.metric(
    "Compradores (1+ pedidos)",
    f"{m['compradores']:,}"
)

c3.metric(
    "Tasa de recompra (2+ pedidos)",
    f"{m['tasa_recompra']:.1f} %"
    if m["tasa_recompra"] is not None else "—"
)

c4.metric(
    "Clientes con exactamente 1 compra",
    f"{m['una_compra']:,}"
)

c5.metric(
    "% de una sola compra entre compradores",
    f"{m['pct_una_compra']:.1f} %"
    if m["pct_una_compra"] is not None else "—"
)

st.caption(
    "Las métricas se calculan sobre la selección actual. "
    "Los porcentajes utilizan como denominador los clientes "
    "con al menos un pedido."
)


# ==================================================
# PUNTOS 3 Y 4. GRAFICOS Y JUSTIFICACIONES
# ==================================================

if m["compradores"] == 0:
    st.warning(
        "No hay compradores con los filtros seleccionados. "
        "Amplíen la ciudad, el canal, el segmento o la preferencia."
    )

else:
    t = tabla_canales(df_sel)

    # PUNTO 3
    st.header("3. Tasa de recompra por canal")

    st.plotly_chart(
        grafico_tasa(t),
        use_container_width=True,
        key="grafico_tasa_kora"
    )

    st.write(
        "**Justificación:** Elegimos un gráfico de barras porque "
        "permite comparar fácilmente el porcentaje de recompra "
        "entre canales. Las barras están ordenadas y muestran "
        "cuántos compradores componen cada tasa, lo que permite "
        "interpretar los porcentajes considerando el tamaño "
        "de cada grupo."
    )

    # PUNTO 4
    st.header("4. Clientes con exactamente una compra por canal")

    st.plotly_chart(
        grafico_una_compra(t),
        use_container_width=True,
        key="grafico_una_compra_kora"
    )

    st.write(
        "**Justificación:** Se utiliza un gráfico de barras "
        "ordenado de mayor a menor para identificar rápidamente "
        "qué canales tienen más clientes con exactamente "
        "un pedido y, por tanto, más compradores potenciales "
        "para una campaña de segunda compra."
    )

    mayor_volumen = t.sort_values(
        "una_compra", ascending=False
    ).iloc[0]

    menor_tasa = t.sort_values(
        "tasa_recompra", ascending=True
    ).iloc[0]

    st.subheader(
        "¿El canal con mayor volumen coincide con el de menor tasa?"
    )

    if (
        mayor_volumen["canal_adquisicion"]
        == menor_tasa["canal_adquisicion"]
    ):
        st.write(
            f"En la selección actual sí coinciden. "
            f"**{mayor_volumen['canal_adquisicion']}** "
            f"tiene {mayor_volumen['una_compra']:,} clientes "
            f"con exactamente una compra y la menor tasa "
            f"de recompra ({mayor_volumen['tasa_recompra']:.1f}%). "
            f"Sin embargo, esto no ocurre necesariamente "
            f"en todos los conjuntos de datos."
        )

    else:
        st.write(
            f"No coinciden. El canal con mayor volumen es "
            f"**{mayor_volumen['canal_adquisicion']}**, "
            f"con {mayor_volumen['una_compra']:,} clientes "
            f"de una compra. La menor tasa corresponde a "
            f"**{menor_tasa['canal_adquisicion']}**, "
            f"con {menor_tasa['tasa_recompra']:.1f}%. "
            f"Esto demuestra que el volumen y la tasa "
            f"representan dimensiones diferentes."
        )

    st.subheader("Resultados por canal")

    st.dataframe(
        t,
        use_container_width=True,
        hide_index=True
    )


# ==================================================
# PUNTO 5. COMPROBACION DE FILTROS
# ==================================================

st.header("5. Comprobación de filtros")

st.write(
    "Los filtros de ciudad, canal, segmento y preferencia "
    "declarada se aplican simultáneamente. Por esta razón, "
    "las métricas y los dos gráficos cambian cuando "
    "se modifica cualquiera de los filtros."
)

# Dos selecciones de prueba
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
        (f"Prueba 1: ciudad {ciudades[0]}", prueba1),
        (
            f"Prueba 2: {canales[0]} / {preferencias[0]}",
            prueba2
        ),
        ("Selección actual", df_sel)
    ]:
        valores = metricas_recompra(datos)

        resultados.append({
            "Selección": nombre,
            "Clientes": valores["clientes"],
            "Compradores": valores["compradores"],
            "Una compra": valores["una_compra"],
            "% una compra": (
                round(valores["pct_una_compra"], 1)
                if valores["pct_una_compra"] is not None
                else None
            ),
            "Tasa recompra (%)": (
                round(valores["tasa_recompra"], 1)
                if valores["tasa_recompra"] is not None
                else None
            )
        })

    st.dataframe(
        pd.DataFrame(resultados),
        use_container_width=True,
        hide_index=True
    )

# Comprobacion sin compradores
vacio = filtrar(
    df, [], canales, segmentos, preferencias
)

m_vacio = metricas_recompra(vacio)

if (
    m_vacio["compradores"] == 0
    and m_vacio["una_compra"] == 0
    and m_vacio["tasa_recompra"] is None
):
    st.info(
        "Prueba sin compradores: correcta. "
        "El resultado es 0 compradores y 0 clientes "
        "con una compra. Los porcentajes quedan "
        "sin definir y no se divide entre cero."
    )


# ==================================================
# PUNTO 6. RECOMENDACION
# ==================================================

st.header("6. Recomendación para el piloto")

if m["compradores"] == 0:
    st.write(
        "No es posible recomendar un canal porque "
        "no hay compradores en la selección actual."
    )

else:
    # Priorizar el canal con mas clientes de una compra.
    # En caso de empate, escoger la menor tasa.
    elegibles = t[t["una_compra"] > 0]

    if elegibles.empty:
        st.write(
            "No hay clientes con exactamente una compra "
            "en la selección actual. No se recomienda "
            "iniciar el piloto con este grupo."
        )
    else:
        candidato = elegibles.sort_values(
            ["una_compra", "tasa_recompra"],
            ascending=[False, True]
        ).iloc[0]

        canal = candidato["canal_adquisicion"]
        cantidad = int(candidato["una_compra"])
        tasa = candidato["tasa_recompra"]

        st.success(
            f"Recomendamos iniciar un piloto de segunda compra "
            f"en **{canal}**, porque tiene "
            f"**{cantidad:,} clientes con exactamente un pedido** "
            f"y una **tasa de recompra de {tasa:.1f}%**. "
            f"Este canal ofrece un grupo de compradores "
            f"potenciales para incentivar nuevas compras. "
            f"Sin embargo, una limitación es que algunos "
            f"clientes han tenido menos tiempo para volver "
            f"a comprar y las diferencias entre canales "
            f"no demuestran causalidad. Para evaluar "
            f"el piloto, mediríamos la tasa de segunda compra "
            f"de quienes reciben la campaña y la "
            f"compararíamos con un grupo de control."
        )


# ==================================================
# NOTA FINAL
# ==================================================

st.caption(
    "Fecha de corte: 31/10/2026. "
    "Comprador = cliente con al menos un pedido. "
    "Los resultados son descriptivos y no prueban causalidad."
)
