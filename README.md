
# EDA · Campañas de marketing telefónico de un banco portugués

Análisis exploratorio de datos (EDA) en **Python + pandas** sobre las campañas de marketing directo de una entidad bancaria portuguesa, cuyo objetivo era que los clientes contrataran un **depósito a plazo**.

**Pregunta de negocio:** ¿qué características del cliente, de la forma de contactarlo y del contexto económico se asocian a que acabe suscribiendo el depósito?

---

## Índice

1. [Estructura del repositorio](#1-estructura-del-repositorio)
2. [Cómo ejecutar el proyecto](#2-cómo-ejecutar-el-proyecto)
3. [Datos de partida](#3-datos-de-partida)
4. [Pasos seguidos](#4-pasos-seguidos)
5. [Informe del análisis](#5-informe-del-análisis)
6. [Conclusiones y recomendaciones](#6-conclusiones-y-recomendaciones)
7. [Limitaciones](#7-limitaciones)

---

## 1. Estructura del repositorio

```
eda-bank-marketing/
├── README.md                     <- Este documento (pasos + informe)
├── data/
│   ├── raw/                      <- Datos originales, sin modificar
│   │   ├── bank-additional.csv
│   │   └── customer-details.xlsx
│   └── processed/                <- Datos tras la limpieza
│       ├── bank_clean.csv
│       ├── customers_clean.csv
│       └── bank_customers_clean.csv   <- Dataset final unido (43.000 x 41)
└── notebooks/
    ├── 01_limpieza_transformacion.ipynb
    ├── 02_analisis_descriptivo_visualizacion.ipynb
    └── funciones.py              <- Funciones reutilizables (carga, limpieza, análisis, gráficos)
```

## 2. Cómo ejecutar el proyecto

**Opción A: Google Colab** (no requiere instalar nada)

1. Descargar el repositorio como zip: botón verde **Code → Download ZIP**.
2. En Colab, *Archivo → Subir cuaderno* y elegir `notebooks/01_limpieza_transformacion.ipynb`.
3. Ejecutar la primera celda de código y subir el zip cuando lo pida. La celda descomprime el proyecto y se sitúa en la carpeta correcta.
4. *Entorno de ejecución → Ejecutar todas*.
5. Repetir con `notebooks/02_analisis_descriptivo_visualizacion.ipynb`.

**Opción B: Visual Studio Code / Jupyter en local** (Python 3.10 o superior)

```bash
git clone https://github.com/<tu-usuario>/eda-bank-marketing.git
cd eda-bank-marketing
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install pandas numpy matplotlib seaborn scipy openpyxl jupyter
```

Abrir la carpeta en VS Code y ejecutar los notebooks **en orden**:

1. `01_limpieza_transformacion.ipynb` → lee `data/raw/` y genera los CSV de `data/processed/`.
2. `02_analisis_descriptivo_visualizacion.ipynb` → lee el dataset final y genera el análisis y los gráficos.

El código está probado con pandas 2.2 y pandas 3.0.

## 3. Datos de partida

| Archivo | Contenido | Tamaño |
|---|---|---|
| `bank-additional.csv` | Una fila por cliente contactado: perfil, datos del contacto, indicadores macroeconómicos y resultado (`y`) | 43.000 filas × 24 columnas |
| `customer-details.xlsx` | Ingresos, hijos, visitas web y fecha de alta. **3 hojas** (clientes dados de alta en 2012, 2013 y 2014) | 43.170 filas × 7 columnas |

Ambos se relacionan por el identificador de cliente (`id_` en el CSV, `ID` en el Excel).

## 4. Pasos seguidos

### 4.1 Transformación y limpieza (notebook 01)

**Diagnóstico.** Con una función `resumen_calidad()` (tipo, nulos, % nulos y valores únicos por columna) se detectaron los siguientes problemas:

| Problema detectado | Solución aplicada |
|---|---|
| Columna índice sobrante (`Unnamed: 0`) en ambos archivos | Eliminada |
| Nombres con puntos (`emp.var.rate`) y guion final (`id_`) | Renombrado a *snake_case* (`emp_var_rate`, `id_cliente`) |
| `cons.price.idx`, `cons.conf.idx`, `euribor3m`, `nr.employed` guardadas como **texto con coma decimal** (`"93,994"`) | Convertidas a `float` |
| Categorías con mayúsculas (`MARRIED`, `NONEXISTENT`) y puntos (`admin.`, `basic.4y`) | Pasadas a minúsculas y `_` |
| Fecha en texto con el mes en español (`2-agosto-2019`) | Parseada con un diccionario de meses → `datetime` |
| Faltaban `contact_month` y `contact_year` | Derivadas de `date` |
| `pdays = 999` codifica "nunca contactado" | Pasado a `NaN` + nueva variable `contactado_antes` |
| Excel repartido en 3 hojas | Leídas como diccionario y apiladas con `pd.concat`, guardando el año de la hoja en `anio_alta` |

**Tratamiento de nulos** (decisiones basadas en el análisis, no a ciegas):

| Columna | % nulos | Estrategia | Justificación |
|---|---|---|---|
| `euribor3m` | 21,5 % | Mediana del grupo de indicadores macro (`emp_var_rate`, `cons_conf_idx`, `nr_employed`) | Dentro de cada grupo la desviación típica es casi siempre < 0,1 puntos |
| `cons_price_idx` | 1,1 % | Ídem | Cada grupo macro tiene **un único** IPC → se recupera el valor exacto |
| `age` | 11,9 % | Mediana por profesión (`job`) + indicador `age_imputada` | La mediana va de 25 (*student*) a 59 (*retired*); la mediana global distorsionaría esos grupos |
| `job`, `marital`, `education` | 0,2–4,2 % | Categoría `unknown` | No hay base para inferirlas |
| `default`, `housing`, `loan` | 2,4–20,9 % | Entero *nullable* (`Int8`) con `<NA>` | No se inventan datos binarios |
| `date` | 0,6 % | Se mantiene `NaT` | No se puede reconstruir |

**Valores atípicos.** Detectados con el criterio IQR (por ejemplo, el 7 % de `duration` y el 6 % de `campaign`). Se **mantienen** porque son comportamientos reales (llamadas de hasta 82 minutos, hasta 56 contactos) y son de los casos más informativos; en el análisis se usan medianas y tramos, que son robustos frente a ellos.

**Validaciones automáticas** con `assert`: sin nulos tras imputar, edades en rango, coherencia `pdays`↔`poutcome` y `previous`↔`poutcome`, fechas de alta coherentes con su hoja, IDs únicos, ningún contacto anterior a la fecha de alta.

**Unión.** `merge` *left* con `validate="one_to_one"`: los 43.000 clientes contactados tienen ficha en el Excel (hay 170 clientes en el Excel que no fueron contactados).

**Variables nuevas:** `y_num`, `duration_min`, `grupo_edad`, `grupo_campaign`, `contactado_antes`, `age_imputada`, `hijos_total`, `tiene_hijos`, `grupo_ingresos` (cuartiles), `grupo_web`, `anio_alta`.

**Optimización de memoria:** pasando a `category` las columnas de texto repetitivo y reduciendo los enteros (`int8`/`int16`), el dataset de campañas baja de **32,7 MB a 7,7 MB (−76 %)**.

**Incoherencias detectadas en los datos de origen:**
- La columna `date` está repartida de forma uniforme entre 2015-2019 y los 12 meses, y **no encaja con los indicadores macro**: en un mismo mes aparecen ~110 valores distintos de euríbor (de 0,6 % a 5 %), cuando es un indicador mensual. La fecha no es fiable para analizar estacionalidad.
- `latitude`/`longitude` no están documentadas y corresponden a **EE. UU.** (lat 24–49, lon −125 a −67), no a Portugal. No se usan en el análisis.

### 4.2 Análisis descriptivo y visualización (notebook 02)

1. Variable objetivo y desbalanceo.
2. Estadísticos de las variables numéricas (media, mediana, desviación típica, cuartiles, IQR, asimetría y coeficiente de variación) y comparación entre quienes suscriben y quienes no.
3. Tasa de conversión por perfil del cliente (profesión, educación, estado civil, edad, préstamos).
4. Estrategia de contacto (canal, resultado de la campaña anterior, nº de llamadas).
5. Duración de la llamada.
6. Contexto macroeconómico y matriz de correlación.
7. Variables del Excel y análisis de una **variable de confusión** (año de alta).
8. Cruces de variables con `pivot_table` y segmentos de mayor y menor conversión.
9. Ranking de factores con **test chi-cuadrado** y **V de Cramér**.

### 4.3 Conceptos de Python y pandas aplicados

- **Funciones** documentadas en `notebooks/funciones.py`, reutilizadas por los dos notebooks (sin código duplicado).
- **Diccionarios** para mapeos (meses en español, renombrado de columnas, colores, órdenes de categorías) y **comprensiones** de listas y diccionarios (normalización de nombres, frecuencias, comprobaciones).
- **Manejo de archivos** con `pathlib` (rutas relativas a la raíz del proyecto), lectura de CSV y de Excel multihoja, y escritura de CSV.
- **pandas**: operaciones vectorizadas en lugar de bucles fila a fila (`str.replace`, `apply` por columnas), `groupby` + `transform` para imputar por grupo, `agg` con varias funciones, `pd.cut` / `pd.qcut`, `pivot_table`, `crosstab`, `merge` con validación, `concat`, `assign`, `pipe`, tipos `category` e `Int8` *nullable*.

---

## 5. Informe del análisis

> Los 12 gráficos que acompañan a este informe están en el notebook `02_analisis_descriptivo_visualizacion.ipynb`.

### 5.1 La conversión es baja: solo 1 de cada 9

De 43.000 clientes contactados, **4.844 (11,3 %) suscribieron** el depósito. Al estar el dataset tan desbalanceado, todo el análisis compara la **tasa de conversión de cada grupo con esta media global**.

### 5.2 Estadística descriptiva

| Variable | Media | Mediana | Desv. típica | Mín | Máx | Asimetría |
|---|---|---|---|---|---|---|
| `age` | 39,8 | 38 | 10,0 | 17 | 98 | 0,88 |
| `duration` (s) | 257,7 | 179 | 258,7 | 0 | 4.918 | 3,32 |
| `campaign` | 2,57 | 2 | 2,77 | 1 | 56 | 4,77 |
| `previous` | 0,17 | 0 | 0,50 | 0 | 7 | 3,83 |
| `euribor3m` (%) | 3,62 | 4,86 | 1,74 | 0,63 | 5,04 | −0,70 |
| `income` (€) | 93.241 | 93.051 | 50.498 | 5.841 | 180.802 | 0,00 |
| `num_web_visits_month` | 16,6 | 17 | 9,2 | 1 | 32 | −0,01 |

- `duration` y `campaign` son muy asimétricas (coef. de variación > 100 %): la **mediana** es más representativa que la media.
- El euríbor es **bimodal**: unas campañas se hicieron con tipos de ~5 % y otras con tipos de ~1 %.
- `income` y `num_web_visits_month` siguen una distribución **uniforme**, poco habitual en datos reales.

Quienes suscriben tienen llamadas mucho más largas (mediana **449 s vs 163 s**) y fueron contactados con un euríbor mucho más bajo (**1,27 % vs 4,86 %**). La edad mediana es casi igual (37 vs 38), aunque, como se ve abajo, la relación con la edad no es lineal.

### 5.3 Perfil del cliente: la edad tiene forma de U

| Grupo de edad | <25 | 25-34 | 35-44 | 45-54 | 55-64 | 65+ |
|---|---|---|---|---|---|---|
| Tasa de suscripción | **23,7 %** | 12,2 % | 9,1 % | 8,7 % | 14,6 % | **46,3 %** |

- Los **mayores de 65** convierten 4 veces más que la media y los **menores de 25**, el doble. La franja 35-54 años, que es el 59 % de los contactos, es la que menos convierte.
- Coherente con lo anterior: **estudiantes (31,3 %)** y **jubilados (25,2 %)** lideran por profesión; **blue-collar (6,9 %)**, *services* (8,1 %) y *entrepreneur* (8,3 %) están a la cola.
- Los solteros convierten más (13,9 %) que casados y divorciados (10,2 %). La educación influye poco (universitarios 13,7 % frente a básica 7,8–10,3 %).
- Tener hipoteca o préstamo apenas cambia la tasa (10,9–11,6 %). `default` no aporta información: solo 3 clientes tienen impagos.

### 5.4 Estrategia de contacto: móvil, historial y no insistir

- **Canal:** el **móvil convierte un 14,7 %** frente al 5,2 % del fijo (casi el triple). Se mantiene entre clientes sin historial previo (11,7 % vs 4,6 %).
- **Historial:** si la campaña anterior fue un **éxito, el 65,3 % vuelve a suscribir**. Los clientes ya contactados antes convierten un **64 %** frente al 9 % de los nuevos.
- **Insistencia:** la conversión **cae con cada llamada**: 13,0 % con 1 contacto → 8,6 % con 4-5 → 6,4 % con 6-10 → **3,0 % con más de 10**.

### 5.5 Duración de la llamada

**Ninguna llamada de menos de 1 minuto acabó en suscripción**; las de más de 10 minutos convierten un 45–59 %. Es la variable más correlacionada con el resultado (r = 0,41), pero **solo se conoce cuando la llamada ha terminado**: refleja el interés del cliente y no sirve para decidir a quién llamar.

### 5.6 El contexto económico es decisivo

Los indicadores macroeconómicos están muy correlacionados entre sí (euríbor–tasa de empleo 0,97; euríbor–nº de empleados 0,95) y todos se relacionan **negativamente** con la suscripción (`nr_employed` −0,36; `euribor3m` −0,31; `emp_var_rate` −0,30).

| Euríbor 3M | Contactos | Tasa | % por móvil | % con historial |
|---|---|---|---|---|
| < 1 % | 4.121 | **45,8 %** | 84,8 % | 27,8 % |
| 1–2 % | 10.038 | 15,7 % | 92,4 % | 4,1 % |
| > 2 % | 28.841 | **4,8 %** | 50,7 % | 0,1 % |

Con tipos bajos y empleo cayendo, la conversión **se multiplica por casi 10**. Dos explicaciones complementarias: en épocas de crisis los ahorradores buscan productos seguros, y en esos periodos el banco hizo **menos llamadas pero mejor dirigidas** (más móvil y más clientes con historial).

La **fecha** del contacto no muestra ningún patrón (tasa entre 10,3 % y 12,4 % en todos los años y meses), lo que confirma que la columna `date` no refleja el momento real de la campaña.

### 5.7 Datos del Excel: poco informativos

Ingresos, nº de hijos y visitas web dan tasas entre **10,8 % y 11,7 %**, es decir, iguales a la media, con correlación ≈ 0 con todas las variables. Además, los ingresos medianos son casi idénticos en todas las profesiones (de 92.000 a 97.000 €, incluso en estudiantes y desempleados). Todo indica que **estas variables son sintéticas** y no reflejan el comportamiento real.

**El año de alta, un caso de variable de confusión:**

A primera vista, los clientes dados de alta en 2014 convierten un 23 % frente al 4,6 % de los de 2012. Pero **el 100 % de los clientes de 2012 fueron contactados con el euríbor por encima del 2 %**, y el 91 % de los de 2014 con tipos por debajo del 2 %. Comparando dentro del mismo contexto (euríbor > 2 %), los tres años convierten igual (4,6 %, 5,4 % y 4,8 %). **La diferencia la explica el contexto económico, no la antigüedad del cliente.**

### 5.8 Cruces de variables

- Los mayores de 65 convierten un **48 % por móvil** y un 32 % incluso por fijo.
- Un éxito previo eleva la conversión al **60–77 % en todas las edades**.
- El segmento menos eficaz es el de 35–54 años contactado por fijo y sin historial (~4 %), que concentra miles de llamadas.

### 5.9 Ranking de factores

| Fuerza (V de Cramér) | Variables |
|---|---|
| Alta (> 0,3) | duración, euríbor, contactado antes, resultado anterior |
| Media (0,14–0,26) | año de alta *(confusión)*, edad, profesión, canal |
| Baja (0,05–0,07) | nº de contactos, educación, estado civil |
| Nula (< 0,02) | vivienda, préstamo, ingresos, hijos, visitas web, mes |

---

## 6. Conclusiones y recomendaciones

**Conclusiones**

1. La tasa de suscripción es baja (**11,3 %**), así que mejorar la segmentación tiene mucho margen.
2. El **contexto económico** es el factor más potente: con euríbor < 1 % convierte el 46 % de los contactos, con euríbor > 2 % solo el 4,8 %.
3. El **historial con el cliente** es el mejor predictor que el banco puede usar antes de llamar: un éxito previo da un 65 % de conversión.
4. La **edad tiene forma de U**: menores de 25 y, sobre todo, mayores de 65 son los segmentos más receptivos.
5. El **móvil casi triplica** la conversión del fijo.
6. **Insistir no compensa**: a partir de 3-4 llamadas la tasa cae por debajo de la media y con más de 10, al 3 %.
7. Ingresos, hijos y visitas web **no ayudan** a explicar la suscripción, y el año de alta es una variable de confusión.

**Recomendaciones de negocio**

- **Priorizar** a clientes con éxito en campañas anteriores, mayores de 60 años, jubilados y estudiantes.
- **Usar el móvil** como canal principal.
- **Limitar** el número de llamadas por cliente a 3 o 4 por campaña y redirigir ese esfuerzo a clientes nuevos con mejor perfil.
- **Intensificar** las campañas de depósitos cuando los tipos de interés bajen y el empleo se deteriore, y reducir el volumen cuando los tipos estén altos.
- **Revisar la calidad de los datos** en origen (fecha del contacto, coordenadas y variables del Excel) antes de usarlos para segmentar o construir un modelo.

**Siguientes pasos posibles:** construir un modelo predictivo (por ejemplo, regresión logística) **sin** la variable `duration`, para puntuar a los clientes antes de llamarles.

## 7. Limitaciones

- Análisis **descriptivo**: las asociaciones encontradas no implican causalidad.
- La fecha del contacto no es coherente con los indicadores macro, así que no se ha podido estudiar la estacionalidad.
- Las variables del Excel parecen generadas aleatoriamente, lo que limita las conclusiones sobre ingresos y hogar.
- Las imputaciones (edad, euríbor) introducen una pequeña incertidumbre; para la edad se guarda un indicador (`age_imputada`) que permite repetir el análisis sin los valores imputados.

---

**Herramientas:** Python · pandas · NumPy · Matplotlib · Seaborn · SciPy · Jupyter · Visual Studio Code
