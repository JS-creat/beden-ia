import os
import pymysql
from dotenv import load_dotenv

# Cargar las variables del .env
load_dotenv()

def get_db_connection():
    """
    Establece una conexión segura con la base de datos MySQL de B-EDEN.
    """
    try:
        connection = pymysql.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            user=os.getenv("DB_USERNAME", "root"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_DATABASE"),
            port=int(os.getenv("DB_PORT", 3306)),
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except pymysql.MySQLError as e:
        print(f"🚨 Error crítico al conectar a la base de datos: {e}")
        raise e

def obtener_catalogo_existencias():
    """
    Consulta el inventario uniendo producto y variantes usando los nombres exactos,
    incluyendo precios de oferta y la marca del producto.
    """
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # Tu SQL real calibrado con tus imágenes
            sql = """
                SELECT 
                    p.nombre_producto,
                    p.marca,
                    p.precio,
                    p.precio_oferta,
                    pv.talla,
                    pv.color,
                    pv.stock
                FROM producto p
                INNER JOIN producto_variante pv ON p.id_producto = pv.id_producto
                WHERE pv.stock > 0 AND p.estado_producto = 1
            """
            cursor.execute(sql)
            resultados = cursor.fetchall()
            
            if not resultados:
                return "Actualmente no hay productos disponibles en el inventario de B-EDEN."
            
            lineas_catalogo = []
            for item in resultados:
                precio_final = f"S/. {item['precio']}"
                if item['precio_oferta'] and float(item['precio_oferta']) > 0:
                    precio_final = f"S/. {item['precio_oferta']} (Precio regular: S/. {item['precio']})"
                
                linea = f"- {item['nombre_producto']} [Marca: {item['marca']}] | Color: {item['color']} | Talla: {item['talla']} | Precio: {precio_final} | Stock: {item['stock']} unids."
                lineas_catalogo.append(linea)
            
            return "\n".join(lineas_catalogo)
            
    except Exception as e:
        print(f"🚨 Error al leer el catálogo de la BD: {e}")
        return "Error al cargar el catálogo de productos en tiempo real."
    finally:
        if connection:
            connection.close()