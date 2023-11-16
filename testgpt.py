from flask import Flask, render_template, request
import matplotlib.pyplot as plt
import pandas as pd
import os
import matplotlib
import csv
matplotlib.use('Agg')  # Usa el backend 'Agg' para la generación de gráficos
from html import escape
import plotly.express as px
import json


app = Flask(__name__)


@app.after_request

def no_cache(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, public, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

with open('final.csv', 'r', newline='', encoding='utf-8') as csvfile:
    # Lee el archivo CSV en un DataFrame, especificando el separador
    df = pd.read_csv(csvfile, sep=',', quotechar='"')

# Convierte las columnas numéricas a tipos de datos numéricos
df['RAM (GB)'] = pd.to_numeric(df['RAM (GB)'], errors='coerce')  # Usamos 'coerce' para manejar errores de conversión
df['Espacio Libre (GB)'] = df['Espacio Libre (GB)'].str.split(', ').apply(lambda x: sum(float(val.replace(',', '.')) for val in x))

# Elimina las comillas de las columnas que contienen cadenas
df['IP'] = df['IP'].str.strip('"')
df['Nombre del Servidor'] = df['Nombre del Servidor'].str.strip('"')
# Haz lo mismo para las otras columnas que puedan tener comillas
print(df.dtypes)


def extract_vlan(ip_address):
    vlan_prefixes = ['10.0.103.', '150.150.150.', '192.168.100.', '10.1.103.', '10.7.103.', '10.3.103.', '10.6.103.', '10.8.103.']
    for prefix in vlan_prefixes:
        if ip_address.startswith(prefix):
            return prefix  # O puedes devolver un identificador de VLAN más específico si es necesario
    return "Desconocido"  # Devuelve un valor predeterminado si no coincide con ningún prefijo

# Agrega una nueva columna al DataFrame para la VLAN
df['VLAN'] = df['IP'].apply(extract_vlan)

@app.route('/')
def index():
    #sistemas_operativos = [escape(so) for so in df['Sistema Operativo'].unique()] 
    
    sistemas_operativos_agrupados = [escape(so) for so in df['Sistema Operativo Agrupado'].unique()]  # Usa la columna correcta aquí # Escapa los nombres de sistema operativo
    return render_template('index.html', sistemas_operativos_agrupados=sistemas_operativos_agrupados)

def guardar_grafico_torta_por_vlan(df_vlan, vlan):
    plt.figure(figsize=(6, 4))
    # Asumiendo que df_vlan es un DataFrame filtrado por una VLAN específica y que 'vlan' es un string con el nombre de la VLAN
    eset_installed_count = df_vlan[df_vlan['ESET Instalado'] == True].shape[0]
    eset_not_installed_count = df_vlan[df_vlan['ESET Instalado'] == False].shape[0]

    # Si no hay datos para la VLAN, no generamos el gráfico
    if eset_installed_count == 0 and eset_not_installed_count == 0:
        return None

    labels = ['ESET Instalado', 'ESET No Instalado']
    sizes = [eset_installed_count, eset_not_installed_count]
    colors = ['#00498F', '#EC3943']  # Verde para instalado, Rojo para no instalado
    
    explode = (0.1, 0)  # 'explode' para destacar el segmento de ESET instalado

    plt.clf()  # Limpia la figura actual para evitar la superposición de gráficos si se llama múltiples veces
    plt.pie(sizes, explode=explode, labels=labels, autopct='%1.1f%%', shadow=True, startangle=90)
    plt.title(f'Distribución de ESET en VLAN {vlan}')
    
    pie_chart_filename = f'vlan_{vlan}_pie_chart.png'
    pie_chart_path = os.path.join('static', pie_chart_filename)
    plt.savefig(pie_chart_path)
    plt.close()

    return pie_chart_filename

@app.route('/filtro', methods=['POST'])

def filtro():
    #sistema_operativo_seleccionado = request.form.get('sistema_operativo_agrupado')
    sistema_operativo_seleccionado = request.form.get('sistema_operativo') 
    sistemas_operativos_agrupados = df['Sistema Operativo Agrupado'].unique()
    df_filtrado = df.copy()  # Crea una copia para trabajar con ella
    if sistema_operativo_seleccionado and sistema_operativo_seleccionado != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Sistema Operativo Agrupado'] == sistema_operativo_seleccionado]
    
    df_conteo_so = df_filtrado['Sistema Operativo Agrupado'].value_counts().reset_index()
    df_conteo_so.columns = ['Sistema Operativo', 'Total Servidores']  # Ajusta el DataFrame para el gráfico treemap
    

    # Calcular estadísticas por VLAN
    vlan_stats = {}
    for vlan in df['VLAN'].unique():
        vlan_df = df_filtrado[df_filtrado['VLAN'] == vlan]
        eset_installed = (vlan_df['ESET Instalado'] == True).sum()
        eset_not_installed = (vlan_df['ESET Instalado'] == False).sum()
        total_vlan = vlan_df.shape[0]
        percentage = (total_vlan / df_filtrado.shape[0] * 100) if df_filtrado.shape[0] > 0 else 0
        pie_chart_filename = guardar_grafico_torta_por_vlan(vlan_df, vlan) if total_vlan > 0 else None
        vlan_stats[vlan] = {
            'total': total_vlan,
            'eset_installed': eset_installed,
            'eset_not_installed': eset_not_installed,
            'percentage': percentage,
            'pie_chart_filename': pie_chart_filename
        }
    
    # Calcular el recuento de servidores con ESET instalado y sin ESET instalado en el DataFrame filtrado
    eset_true_count = (df_filtrado['ESET Instalado'] == True).sum()
    eset_false_count = (df_filtrado['ESET Instalado'] == False).sum()
    treemap_filename = guardar_grafico_treemap(df_conteo_so, sistema_operativo_seleccionado)  # Pasa el DataFrame ajustado
    # Generar el gráfico de torta para "Todos" si no se seleccionó un sistema operativo específico
    if sistema_operativo_seleccionado == "":
        pie_filename = guardar_grafico_torta(df_filtrado['ESET Instalado'].sum(), df_filtrado.shape[0] - df_filtrado['ESET Instalado'].sum(), "Todos")
    else:
        total_servidores_con_so = df_filtrado.shape[0]
        pie_filename = guardar_grafico_torta(eset_true_count, eset_false_count, sistema_operativo_seleccionado)

    return render_template('index.html',
                           sistemas_operativos=df['Sistema Operativo Agrupado'].unique(),
                           sistemas_operativos_agrupados=sistemas_operativos_agrupados,
                           sistema_operativo_seleccionado=sistema_operativo_seleccionado if sistema_operativo_seleccionado else "Todos",
                           eset_true_count=eset_true_count,
                           eset_false_count=eset_false_count,
                           pie_filename=pie_filename,  # Asegúrate de pasar esta variable a la plantilla
                           total_servidores=df.shape[0],
                           cantidad_seleccionada=df_filtrado.shape[0],
                           porcentaje_seleccionado=(df_filtrado.shape[0] / df.shape[0] * 100) if df.shape[0] > 0 else 0,
                           vlan_data=vlan_stats,
                           treemap_filename=treemap_filename)















def contar_sistemas_operativos(df):
    return df['Sistema Operativo'].value_counts()
conteo_so = contar_sistemas_operativos(df)
df_conteo_so = conteo_so.reset_index()  # Convierte la serie en un DataFrame
df_conteo_so.columns = ['Sistema Operativo', 'Total Servidores']  # Nombra las columnas


def guardar_grafico_treemap(df_conteo_so, sistema_operativo_seleccionado):
    # Definir el mapeo de colores
    colors = {
        'Microsoft Windows Server 2019': '#008000', 
        'Microsoft Windows Server 2016': '#008000',
        'Microsoft Windows Server 2012': '#f7ff00',
        'Microsoft Windows Server 2008': '#ff0000',
        'Microsoft Windows Server 2003': '#ff0000',
        'Microsoft Windows XP': '#ff0000',
        'Microsoft Windows 10': '#ff0000'
    }
    
    # Mapea cada sistema operativo a su color correspondiente
    df_conteo_so['color'] = df_conteo_so['Sistema Operativo'].map(colors)
    
    # Crear la figura con Plotly, pasando la columna 'color' al argumento 'color'
    fig = px.treemap(df_conteo_so, path=['Sistema Operativo'], values='Total Servidores', 
                     color='Sistema Operativo',  # Indica la columna para determinar el color
                     color_discrete_map=colors,  # Pasa el diccionario de colores
                     title="Distribución de Servidores por Sistema Operativo"
                    )
    
    # Especifica el nombre del archivo de salida
    treemap_filename = "treemap.html"
    treemap_path = os.path.join('static', treemap_filename)
    
    # Guardar la figura como archivo HTML
    with open(treemap_path, 'w') as f:
        f.write(fig.to_html(full_html=False, include_plotlyjs='cdn'))
    
    # Devolver el nombre del archivo para que pueda ser utilizado en la plantilla HTML
    return treemap_filename



def agrupar_por_año(so_nombre):
    # Crear un mapeo de versiones a años simplificado
    version_a_año = {
        '2003': 'Microsoft Windows Server 2003',
        '2008': 'Microsoft Windows Server 2008',  # Aquí '2008 R2' también se considera '2008'
        '2012': 'Microsoft Windows Server 2012',  # Aquí '2012 R2' también se considera '2012'
        '2016': 'Microsoft Windows Server 2016',
        '2019': 'Microsoft Windows Server 2019',
        'XP': 'Microsoft Windows XP',
        '10': 'Microsoft Windows 10',
    }
    # Normalizar el nombre del sistema operativo
    for version in version_a_año.keys():
        # Buscar por la clave y "R2" como una posibilidad adicional
        if version in so_nombre or (version + " R2") in so_nombre:
            return version_a_año[version]
    # Si no se encuentra una coincidencia, devolver el nombre original
    return so_nombre

# Aplicar la función al DataFrame
df['Sistema Operativo Agrupado'] = df['Sistema Operativo'].apply(agrupar_por_año)



@app.route('/informe')
def informe():

    df_html = df.to_html(border=0, index=False, classes='dataframe', escape=False)
    # Renderiza la plantilla 'informe.html' con el DataFrame convertido en HTML
    return render_template('informe.html', df_html=df_html)

# Función para guardar el gráfico de torta de comparación de ESET instalado
def guardar_grafico_torta(total_eset_instalado, total_eset_no_instalado, sistema_operativo_seleccionado):
    print("Generando gráfico de torta...")  # Impresión para depuración
    
    # Validar que los totales no sean NaN y sean al menos 0
    total_eset_instalado = 0 if pd.isna(total_eset_instalado) else total_eset_instalado
    total_eset_no_instalado = 0 if pd.isna(total_eset_no_instalado) else total_eset_no_instalado

    # Si no hay servidores, evita la generación del gráfico
    if total_eset_instalado == 0 and total_eset_no_instalado == 0:
        print("No hay datos para mostrar en el gráfico de torta.")
        return None

    fig, ax = plt.subplots(figsize=(6, 4))
    labels = ['ESET Instalado', 'ESET No Instalado']
    sizes = [total_eset_instalado, total_eset_no_instalado]  # Asegúrate de que el orden de los tamaños sea el correcto
    colors = ['#00498F', '#EC3943']  # Verde para instalado, Rojo para no instalado
    explode = (0.1, 0)  # Solo destaca la porción de ESET instalado

    ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%', shadow=True, startangle=90)
    ax.axis('equal')  # Mantiene el gráfico de torta circular

    pie_filename = "comparacion_sistema_operativo.png"
    pie_path = os.path.join('static', pie_filename)
    plt.savefig(pie_path)
    plt.close()
    print("Gráfico de torta guardado en:", pie_path)  # Confirma la ruta del archivo guardado
    return pie_filename

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)

