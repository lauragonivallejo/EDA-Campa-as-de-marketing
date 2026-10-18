"""
Funciones reutilizables para el EDA de campañas de marketing bancario.

Se agrupan aquí para no duplicar código entre notebooks:
- carga de datos en bruto
- limpieza y transformación de cada dataset
- utilidades de análisis (tasas de conversión) y de visualización
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Rutas del proyecto
# ---------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parents[1]
RUTA_RAW = RAIZ / "data" / "raw"
RUTA_PROCESSED = RAIZ / "data" / "processed"
RUTA_FIGURAS = RAIZ / "reports" / "figures"

# ---------------------------------------------------------------------------
# Constantes y diccionarios de mapeo
# ---------------------------------------------------------------------------
MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

# Columnas numéricas que vienen como texto con coma decimal ("93,994")
COLS_COMA_DECIMAL = ["cons_price_idx", "cons_conf_idx", "euribor3m", "nr_employed"]

# Variables macroeconómicas: describen el contexto del mes, no al cliente
COLS_MACRO = ["emp_var_rate", "cons_price_idx", "cons_conf_idx", "euribor3m", "nr_employed"]

COLS_CATEGORICAS = ["job", "marital", "education", "contact", "poutcome"]
COLS_BINARIAS = ["default", "housing", "loan"]

ORDEN_EDUCACION = [
    "illiterate", "basic_4y", "basic_6y", "basic_9y",
    "high_school", "professional_course", "university_degree", "unknown",
]

# Paleta (validada para daltonismo en pares adyacentes)
COLOR_PRINCIPAL = "#2a78d6"   # azul
COLOR_SECUNDARIO = "#eb6834"  # naranja
COLOR_NEUTRO = "#8a8984"      # gris para referencias (media global)
COLORES_Y = {"no": COLOR_PRINCIPAL, "yes": COLOR_SECUNDARIO}


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------
def cargar_bank(ruta: Path = RUTA_RAW / "bank-additional.csv") -> pd.DataFrame:
    """Lee el CSV de campañas tal cual viene (sin transformar)."""
    return pd.read_csv(ruta)


def cargar_customers(ruta: Path = RUTA_RAW / "customer-details.xlsx") -> pd.DataFrame:
    """Lee las 3 hojas del Excel y las apila en un único DataFrame.

    sheet_name=None devuelve un diccionario {nombre_hoja: DataFrame}; se añade
    el nombre de la hoja como columna 'anio_alta' para no perder ese dato.
    """
    hojas = pd.read_excel(ruta, sheet_name=None)
    return pd.concat(
        [hoja.assign(anio_alta=int(nombre)) for nombre, hoja in hojas.items()],
        ignore_index=True,
    )


# ---------------------------------------------------------------------------
# Diagnóstico
# ---------------------------------------------------------------------------
def resumen_calidad(df: pd.DataFrame) -> pd.DataFrame:
    """Tabla de calidad por columna: tipo, nulos, % nulos y valores únicos."""
    return (
        pd.DataFrame({
            "tipo": df.dtypes.astype(str),
            "nulos": df.isna().sum(),
            "pct_nulos": (df.isna().mean() * 100).round(2),
            "valores_unicos": df.nunique(),
        })
        .sort_values("pct_nulos", ascending=False)
    )


def memoria_mb(df: pd.DataFrame) -> float:
    """Memoria ocupada por un DataFrame en MB (contando strings)."""
    return round(df.memory_usage(deep=True).sum() / 1024 ** 2, 2)


# ---------------------------------------------------------------------------
# Limpieza: bank-additional
# ---------------------------------------------------------------------------
def normalizar_nombres(columnas) -> list:
    """snake_case: minúsculas, sin puntos ni espacios ni guiones bajos finales."""
    return [c.strip().lower().replace(".", "_").replace(" ", "_").strip("_") for c in columnas]


def texto_a_float(serie: pd.Series) -> pd.Series:
    """Convierte números con coma decimal ('93,994') a float."""
    return pd.to_numeric(serie.str.replace(",", ".", regex=False), errors="coerce")


def parsear_fecha_es(serie: pd.Series) -> pd.Series:
    """Convierte fechas tipo '2-agosto-2019' a datetime usando MESES_ES."""
    partes = serie.str.split("-", expand=True)
    return pd.to_datetime(
        pd.DataFrame({
            "year": pd.to_numeric(partes[2]),
            "month": partes[1].str.lower().map(MESES_ES),
            "day": pd.to_numeric(partes[0]),
        }),
        errors="coerce",
    )


def limpiar_bank(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Aplica todas las transformaciones de limpieza al dataset de campañas.

    Pasos (cada uno documentado en el notebook 01):
      1. Eliminar la columna índice sobrante y normalizar nombres.
      2. Convertir a float las columnas con coma decimal.
      3. Homogeneizar texto en categóricas (minúsculas, sin puntos).
      4. Parsear la fecha y derivar contact_month / contact_year.
      5. Tratar nulos (imputación por grupo o categoría 'unknown').
      6. Recodificar pdays=999 y la variable objetivo.
      7. Crear variables derivadas y optimizar tipos.
    """
    df = df_raw.drop(columns=["Unnamed: 0"], errors="ignore").copy()
    df.columns = normalizar_nombres(df.columns)
    df = df.rename(columns={"id": "id_cliente"})

    # 2. Numéricas con coma decimal
    df[COLS_COMA_DECIMAL] = df[COLS_COMA_DECIMAL].apply(texto_a_float)

    # 3. Texto homogéneo: 'MARRIED' -> 'married', 'basic.4y' -> 'basic_4y', 'admin.' -> 'admin'
    for col in COLS_CATEGORICAS:
        df[col] = (
            df[col].str.strip().str.lower()
            .str.rstrip(".").str.replace(".", "_", regex=False)
        )

    # 4. Fechas
    df["date"] = parsear_fecha_es(df["date"])
    df["contact_year"] = df["date"].dt.year.astype("Int16")
    df["contact_month"] = df["date"].dt.month.astype("Int8")

    # 5. Nulos
    df = imputar_nulos_bank(df)

    # 6. Recodificaciones
    df["contactado_antes"] = (df["pdays"] != 999).astype("int8")
    df["pdays"] = df["pdays"].replace(999, np.nan)  # 999 = "nunca contactado", no un valor real
    df["y_num"] = (df["y"] == "yes").astype("int8")

    # 7. Variables derivadas
    df["duration_min"] = (df["duration"] / 60).round(2)
    df["grupo_edad"] = pd.cut(
        df["age"], bins=[0, 25, 35, 45, 55, 65, 120],
        labels=["<25", "25-34", "35-44", "45-54", "55-64", "65+"], right=False,
    )
    df["grupo_campaign"] = pd.cut(
        df["campaign"], bins=[0, 1, 2, 3, 5, 10, np.inf],
        labels=["1", "2", "3", "4-5", "6-10", ">10"],
    )
    return optimizar_tipos(df)


def imputar_nulos_bank(df: pd.DataFrame) -> pd.DataFrame:
    """Estrategia de nulos justificada por el diagnóstico del notebook 01."""
    df = df.copy()

    # age (~12% nulos): la edad depende mucho de la profesión (student ~25, retired ~59),
    # así que se imputa con la mediana de su 'job'; se guarda un indicador.
    df["age_imputada"] = df["age"].isna().astype("int8")
    df["age"] = df["age"].fillna(df.groupby("job")["age"].transform("median"))
    df["age"] = df["age"].fillna(df["age"].median())  # clientes sin job conocido

    # cons_price_idx: cada combinación (emp_var_rate, cons_conf_idx, nr_employed) tiene
    # un único IPC -> la imputación por grupo recupera el valor exacto.
    # euribor3m (~21% nulos): dentro de cada contexto macro su desviación es < 0.25 pp,
    # por lo que la mediana del grupo es una estimación muy precisa.
    grupo_macro = ["emp_var_rate", "cons_conf_idx", "nr_employed"]
    for col in ["cons_price_idx", "euribor3m"]:
        df[col] = df[col].fillna(df.groupby(grupo_macro)[col].transform("median"))

    # Categóricas: el nulo es información ("no consta"), se mantiene como 'unknown'
    df[["job", "marital", "education"]] = df[["job", "marital", "education"]].fillna("unknown")

    # Binarias: no se inventan valores; se dejan como entero nullable (<NA> = desconocido)
    df[COLS_BINARIAS] = df[COLS_BINARIAS].astype("Int8")
    return df


def optimizar_tipos(df: pd.DataFrame) -> pd.DataFrame:
    """Reduce memoria: categóricas a 'category' y enteros al tipo más pequeño."""
    df = df.copy()
    df[COLS_CATEGORICAS + ["y"]] = df[COLS_CATEGORICAS + ["y"]].astype("category")
    df["education"] = pd.Categorical(df["education"], categories=ORDEN_EDUCACION, ordered=True)
    for col in ["duration", "campaign", "previous"]:
        df[col] = pd.to_numeric(df[col], downcast="integer")
    df["age"] = df["age"].round().astype("int8")
    df["nr_employed"] = df["nr_employed"].astype("float32")
    return df


# ---------------------------------------------------------------------------
# Limpieza: customer-details
# ---------------------------------------------------------------------------
def limpiar_customers(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Limpieza y enriquecimiento del dataset de clientes."""
    df = df_raw.drop(columns=["Unnamed: 0"], errors="ignore").copy()
    renombrar = {
        "Income": "income", "Kidhome": "kidhome", "Teenhome": "teenhome",
        "Dt_Customer": "dt_customer", "NumWebVisitsMonth": "num_web_visits_month",
        "ID": "id_cliente",
    }
    df = df.rename(columns=renombrar)
    df["dt_customer"] = pd.to_datetime(df["dt_customer"])

    # Variables derivadas
    df["hijos_total"] = df["kidhome"] + df["teenhome"]
    df["tiene_hijos"] = (df["hijos_total"] > 0).astype("int8")
    df["grupo_ingresos"] = pd.qcut(df["income"], q=4, labels=["Q1 bajo", "Q2", "Q3", "Q4 alto"])
    df["grupo_web"] = pd.cut(
        df["num_web_visits_month"], bins=[-1, 5, 10, 20, np.inf],
        labels=["0-5", "6-10", "11-20", ">20"],
    )

    enteros = ["kidhome", "teenhome", "hijos_total", "num_web_visits_month", "anio_alta"]
    df[enteros] = df[enteros].apply(pd.to_numeric, downcast="integer")
    df["income"] = pd.to_numeric(df["income"], downcast="integer")
    return df


def cargar_procesado(ruta: Path = RUTA_PROCESSED / "bank_customers_clean.csv") -> pd.DataFrame:
    """Lee el dataset final y restaura los tipos que el CSV no conserva."""
    df = pd.read_csv(ruta, parse_dates=["date", "dt_customer"])
    df = optimizar_tipos(df)
    ordenes = {
        "grupo_edad": ["<25", "25-34", "35-44", "45-54", "55-64", "65+"],
        "grupo_campaign": ["1", "2", "3", "4-5", "6-10", ">10"],
        "grupo_ingresos": ["Q1 bajo", "Q2", "Q3", "Q4 alto"],
        "grupo_web": ["0-5", "6-10", "11-20", ">20"],
    }
    for col, cats in ordenes.items():
        df[col] = pd.Categorical(df[col].astype(str), categories=cats, ordered=True)
    df[COLS_BINARIAS] = df[COLS_BINARIAS].astype("Int8")
    df[["contact_year", "contact_month"]] = df[["contact_year", "contact_month"]].astype("Int16")
    return df


# ---------------------------------------------------------------------------
# Análisis
# ---------------------------------------------------------------------------
def tasa_conversion(df: pd.DataFrame, col, objetivo: str = "y_num", min_n: int = 0) -> pd.DataFrame:
    """Nº de contactos, nº de suscripciones y tasa de conversión (%) por grupo.

    `col` puede ser una columna o una lista de columnas.
    """
    tabla = (
        df.groupby(col, observed=True)[objetivo]
        .agg(contactos="count", suscripciones="sum", tasa="mean")
        .assign(tasa=lambda t: (t["tasa"] * 100).round(2))
    )
    return tabla[tabla["contactos"] >= min_n]


def estadisticos(df: pd.DataFrame, columnas: list) -> pd.DataFrame:
    """Estadísticos descriptivos ampliados (incluye asimetría y coef. de variación)."""
    t = df[columnas].agg(["count", "mean", "median", "std", "min", "max", "skew"]).T
    t["q1"] = df[columnas].quantile(0.25)
    t["q3"] = df[columnas].quantile(0.75)
    t["iqr"] = t["q3"] - t["q1"]
    t["cv_%"] = (t["std"] / t["mean"] * 100)
    return t.round(2)


def asociacion_categoricas(df: pd.DataFrame, columnas: list, objetivo: str = "y") -> pd.DataFrame:
    """Test chi-cuadrado y V de Cramér de cada variable categórica con el objetivo.

    La V de Cramér (0-1) mide la fuerza de la asociación y permite comparar
    variables con distinto nº de categorías.
    """
    from scipy.stats import chi2_contingency

    filas = []
    for col in columnas:
        tabla = pd.crosstab(df[col], df[objetivo])
        chi2, p, _, _ = chi2_contingency(tabla)
        v = np.sqrt(chi2 / (tabla.values.sum() * (min(tabla.shape) - 1)))
        filas.append({"variable": col, "chi2": round(chi2, 1), "p_valor": p, "v_cramer": round(v, 3)})
    return pd.DataFrame(filas).set_index("variable").sort_values("v_cramer", ascending=False)


def outliers_iqr(serie: pd.Series, k: float = 1.5) -> pd.Series:
    """Máscara booleana con los valores fuera de [Q1 - k·IQR, Q3 + k·IQR]."""
    q1, q3 = serie.quantile([0.25, 0.75])
    iqr = q3 - q1
    return (serie < q1 - k * iqr) | (serie > q3 + k * iqr)


# ---------------------------------------------------------------------------
# Visualización
# ---------------------------------------------------------------------------
def estilo_graficos() -> None:
    """Estilo común para todas las figuras (ejes discretos, sin bordes superfluos)."""
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 150, "savefig.bbox": "tight",
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": "#b5b4ae", "axes.labelcolor": "#2b2b29",
        "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlelocation": "left",
        "axes.grid": True, "axes.grid.axis": "y", "grid.color": "#e6e5e0", "grid.linewidth": 0.8,
        "xtick.color": "#52514e", "ytick.color": "#52514e", "font.size": 10,
        "legend.frameon": False,
    })


def guardar(fig, nombre: str) -> Path:
    """Guarda una figura en reports/figures y devuelve la ruta."""
    RUTA_FIGURAS.mkdir(parents=True, exist_ok=True)
    ruta = RUTA_FIGURAS / f"{nombre}.png"
    fig.savefig(ruta)
    return ruta


def barras_conversion(tabla: pd.DataFrame, titulo: str, media_global: float, ax=None,
                      horizontal: bool = True, ordenar: bool = True):
    """Barras de tasa de conversión por grupo con la media global como referencia."""
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 0.4 * len(tabla) + 1.5) if horizontal else (8, 4))
    datos = tabla.sort_values("tasa") if ordenar else tabla
    etiquetas = datos.index.astype(str)
    colores = [COLOR_SECUNDARIO if v > media_global else COLOR_PRINCIPAL for v in datos["tasa"]]

    if horizontal:
        ax.barh(etiquetas, datos["tasa"], color=colores, height=0.7)
        ax.axvline(media_global, color=COLOR_NEUTRO, ls="--", lw=1.2, label=f"media global {media_global:.1f}%")
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", visible=True)
        ax.set_xlabel("Tasa de suscripción (%)")
        for i, v in enumerate(datos["tasa"]):
            ax.text(v + 0.3, i, f"{v:.1f}%", va="center", fontsize=8.5, color="#2b2b29")
    else:
        ax.bar(etiquetas, datos["tasa"], color=colores, width=0.7)
        ax.axhline(media_global, color=COLOR_NEUTRO, ls="--", lw=1.2, label=f"media global {media_global:.1f}%")
        ax.set_ylabel("Tasa de suscripción (%)")
        for i, v in enumerate(datos["tasa"]):
            ax.text(i, v + 0.3, f"{v:.1f}%", ha="center", fontsize=8.5, color="#2b2b29")
    ax.set_ylim(top=ax.get_ylim()[1] * 1.08) if not horizontal else ax.set_xlim(right=ax.get_xlim()[1] * 1.08)
    ax.legend(loc="best", fontsize=8.5)
    ax.set_title(titulo)
    return ax
