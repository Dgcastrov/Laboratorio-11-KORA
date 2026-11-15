import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="KORA", layout="wide")
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



st.divider()
st.header("Respuestas KORA")


# PREGUNTA 1
st.subheader("1. ¿Por qué no basta la tasa de recompra?")

st.write(
    "La tasa de recompra por sí sola no es suficiente para "
    "elegir el mejor canal, porque muestra el porcentaje de "
    "clientes que realizaron dos o más pedidos, pero no indica "
    "cuántos clientes podrían participar en una campaña. "
    "Por eso también debemos considerar el número de clientes "
    "con exactamente una compra, que representa a los "
    "compradores potenciales para realizar una segunda compra."
)

st.write(
    "Tasa de recompra:número de compradores con dos o más "
    "pedidos dividido entre el total de compradores, "
    "multiplicado por 100."
)

st.write(
    "Clientes con exactamente una compra: cantidad de "
    "clientes que realizaron un único pedido hasta la fecha "
    "de corte."
)


# PREGUNTA 2
st.subheader("2. Métricas de clientes con una compra")

st.write(
    f"En la selección actual hay {m['una_compra']:,} clientes "
    f"con exactamente una compra, de un total de "
    f"{m['compradores']:,} compradores."
)

if m["pct_una_compra"] is not None:
    st.write(
        f"Estos representan el {m['pct_una_compra']:.1f}% "
        f"de los compradores seleccionados."
    )
else:
    st.write(
        "No es posible calcular el porcentaje porque "
        "no hay compradores en la selección."
    )


# PREGUNTA 3
st.subheader("3. Gráfico de recompra")

st.write(
    "Elegimos un gráfico de barras porque permite comparar "
    "fácilmente el porcentaje de compradores que realizaron "
    "dos o más pedidos en cada canal. Además, las etiquetas "
    "y la información interactiva muestran cuántos compradores "
    "componen cada tasa, lo que ayuda a interpretar los "
    "porcentajes considerando el tamaño de cada grupo."
)


# PREGUNTA 4
st.subheader("4. Comparación de clientes con una compra")

st.write(
    "El segundo gráfico está ordenado de mayor a menor "
    "para identificar los canales con más clientes que "
    "todavía no realizan una segunda compra."
)

if m["compradores"] > 0:

    t_respuestas = tabla_canales(df_sel)

    mayor_volumen = t_respuestas.sort_values(
        "una_compra", ascending=False
    ).iloc[0]

    menor_tasa = t_respuestas.sort_values(
        "tasa_recompra", ascending=True
    ).iloc[0]

    if (
        mayor_volumen["canal_adquisicion"]
        == menor_tasa["canal_adquisicion"]
    ):
        st.write(
            f"En esta selección sí coinciden. El canal "
            f"{mayor_volumen['canal_adquisicion']} "
            f"tiene el mayor volumen de clientes con "
            f"exactamente una compra "
            f"({mayor_volumen['una_compra']:,} clientes**) "
            f"y la menor tasa de recompra "
            f"({menor_tasa['tasa_recompra']:.1f}%). "
            f"Sin embargo, esto no ocurre necesariamente "
            f"en todos los casos."
        )

    else:
        st.write(
            f"No coinciden. El canal con mayor volumen es "
            f"{mayor_volumen['canal_adquisicion']}, "
            f"con {mayor_volumen['una_compra']:,} clientes "
            f"de una compra. En cambio, la menor tasa de "
            f"recompra corresponde a "
            f"{menor_tasa['canal_adquisicion']}, "
            f"con {menor_tasa['tasa_recompra']:.1f}%. "
            f"Esto demuestra que volumen y tasa son "
            f"medidas diferentes."
        )

else:
    st.write(
        "No hay compradores en la selección actual "
        "para comparar los canales."
    )


# PREGUNTA 5
st.subheader("5. Funcionamiento de los filtros")

st.write(
    "El dashboard permite filtrar por ciudad, canal de "
    "adquisición, segmento y preferencia declarada. "
    "Todos los filtros se aplican simultáneamente, "
    "por lo que las métricas y ambos gráficos "
    "se actualizan según la selección."
)

# Dos selecciones para comprobar los filtros
ciudades = sorted(df["ciudad"].dropna().unique().tolist())
canales = sorted(df["canal_adquisicion"].dropna().unique().tolist())
preferencias = sorted(
    df["preferencia_declarada"].dropna().unique().tolist()
)

if ciudades and canales and preferencias:

    prueba1 = filtrar(
        df,
        [ciudades[0]],
        canales,
        ORDEN_SEGMENTOS,
        preferencias
    )

    prueba2 = filtrar(
        df,
        ciudades,
        [canales[0]],
        ORDEN_SEGMENTOS,
        [preferencias[0]]
    )

    m1 = metricas_recompra(prueba1)
    m2 = metricas_recompra(prueba2)

    st.write(
        f"Prueba 1: al seleccionar la ciudad "
        f"{ciudades[0]}, se obtienen "
        f"{m1['compradores']:,} compradores y "
        f"{m1['una_compra']:,} clientes con una compra."
    )

    st.write(
        f"Prueba 2:al seleccionar el canal "
        f"{canales[0]} y la preferencia "
        f"{preferencias[0]}, se obtienen "
        f"{m2['compradores']:,} compradores y "
        f"{m2['una_compra']:,} clientes con una compra."
    )

# Comprobar selección sin compradores
vacio = filtrar(
    df, [], canales, ORDEN_SEGMENTOS, preferencias
)

m_vacio = metricas_recompra(vacio)

if m_vacio["compradores"] == 0:
    st.write(
        "Prueba sin compradores: cuando la selección "
        "no contiene compradores, las cantidades son cero "
        "y los porcentajes no se calculan. "
        "El dashboard muestra una advertencia y evita "
        "la división entre cero."
    )


# PREGUNTA 6
st.subheader("6. Recomendación para el piloto")

if m["compradores"] > 0:

    t_recomendacion = tabla_canales(df_sel)

    elegibles = t_recomendacion[
        t_recomendacion["una_compra"] > 0
    ]

    if not elegibles.empty:

        recomendado = elegibles.sort_values(
            ["una_compra", "tasa_recompra"],
            ascending=[False, True]
        ).iloc[0]

        canal = recomendado["canal_adquisicion"]
        cantidad = int(recomendado["una_compra"])
        tasa = recomendado["tasa_recompra"]

        st.write(
            f"Recomendamos iniciar un piloto de segunda compra "
            f"en {canal}, porque tiene "
            f"{cantidad:,} clientes con exactamente un pedido "
            f"y una tasa de recompra de {tasa:.1f}%. "
            f"Este canal ofrece una oportunidad para incentivar "
            f"nuevas compras. Sin embargo, una limitación es "
            f"que algunos clientes han tenido menos tiempo "
            f"para volver a comprar, lo que puede afectar "
            f"las comparaciones. Para evaluar el piloto "
            f"mediríamos la tasa de segunda compra de quienes "
            f"reciben la campaña frente a un grupo de control."
        )

    else:
        st.write(
            "No hay clientes con exactamente una compra "
            "en la selección actual para recomendar un piloto."
        )

else:
    st.write(
        "No es posible recomendar un canal porque "
        "no hay compradores en la selección actual."
    )
