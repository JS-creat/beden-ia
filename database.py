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
    Consulta el inventario uniendo producto, variantes, género y categoría,
    lo que permite a Alessia diferenciar ropa de hombre, mujer y tipos de prenda.
    """
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = """
                SELECT 
                    p.nombre_producto,
                    p.marca,
                    p.precio,
                    p.precio_oferta,
                    g.nombre_genero,
                    c.nombre_categoria,
                    pv.talla,
                    pv.color,
                    pv.stock
                FROM producto p
                INNER JOIN producto_variante pv ON p.id_producto = pv.id_producto
                INNER JOIN genero g ON p.id_genero = g.id_genero
                INNER JOIN categoria c ON p.id_categoria = c.id_categoria
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
                
                # Agregamos [Género] y [Categoría] explícitamente en la línea de texto
                linea = (
                    f"- {item['nombre_producto']} [Marca: {item['marca']}] | "
                    f"Para: {item['nombre_genero']} | Categoría: {item['nombre_categoria']} | "
                    f"Color: {item['color']} | Talla: {item['talla']} | "
                    f"Precio: {precio_final} | Stock: {item['stock']} unids."
                )
                lineas_catalogo.append(linea)
            
            return "\n".join(lineas_catalogo)
            
    except Exception as e:
        print(f"🚨 Error al leer el catálogo de la BD: {e}")
        return "Error al cargar el catálogo de productos en tiempo real."
    finally:
        if connection:
            connection.close()

def obtener_pedidos_usuario_completo(user_id: int):
    """
    Trae los 3 últimos pedidos del usuario junto con el desglose de productos,
    motivo de anulación, tipo de entrega (retiro/envío) y distrito de destino.
    """
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # 1. Traer los pedidos principales cruzando tipo_entrega y distrito
            sql_pedidos = """
                SELECT 
                    p.id_pedido,
                    p.numero_pedido, 
                    p.total_pedido, 
                    p.estado_pedido, 
                    p.motivo_anulacion,
                    p.fecha_pedido, 
                    p.fecha_entrega_estimada,
                    p.nombre_agencia,
                    p.direccion_agencia,
                    p.direccion AS direccion_cliente,
                    te.nombre_tipo_entrega,
                    d.nombre_distrito
                FROM pedido p
                INNER JOIN tipo_entrega te ON p.id_tipo_entrega = te.id_tipo_entrega
                LEFT JOIN distrito d ON p.id_distrito = d.id_distrito
                WHERE p.id_usuario = %s 
                ORDER BY p.fecha_pedido DESC 
                LIMIT 3
            """
            cursor.execute(sql_pedidos, (user_id,))
            pedidos = cursor.fetchall()
            
            if not pedidos:
                return "El usuario no tiene ningún pedido registrado en su cuenta todavía."
            
            lineas_reporte = []
            
            # 2. Iterar cada pedido y jalar sus detalles de productos
            for p in pedidos:
                fecha = p['fecha_pedido'].strftime('%d/%m/%Y') if p['fecha_pedido'] else "No registrada"
                entrega_est = p['fecha_entrega_estimada'].strftime('%d/%m/%Y') if p['fecha_entrega_estimada'] else "Pendiente"
                distrito_destino = p['nombre_distrito'] or "No especificado"
                
                # Base de la información del pedido
                info_pedido = (
                    f"📦 PEDIDO N°: {p['numero_pedido']} |\n"
                    f"   - Estado Actual: {p['estado_pedido']}\n"
                    f"   - Tipo de Entrega: {p['nombre_tipo_entrega']}\n"
                )
                
                # Si el pedido fue anulado, incluimos el motivo
                if p['motivo_anulacion']:
                    info_pedido += f"   - ⚠️ MOTIVO DE ANULACIÓN: {p['motivo_anulacion']}\n"
                
                # Ajustamos el texto según el tipo de entrega
                if "tienda" in p['nombre_tipo_entrega'].lower() or "retiro" in p['nombre_tipo_entrega'].lower():
                    info_pedido += f"   - Punto de Recojo: Retiro en Tienda Principal B-EDEN\n"
                else:
                    agencia = p['nombre_agencia'] or "Agencia por asignar"
                    dir_agencia = p['direccion_agencia'] or "Dirección de agencia pendiente"
                    info_pedido += (
                        f"   - Enviar por: {agencia}\n"
                        f"   - Dirección Agencia: {dir_agencia}\n"
                        f"   - Distrito Destino: {distrito_destino}\n"
                        f"   - Dirección de Entrega Casa/Oficina: {p['direccion_cliente'] or 'No aplica'}\n"
                    )
                    
                info_pedido += (
                    f"   - Total Pagado: S/. {p['total_pedido']}\n"
                    f"   - Fecha de Compra: {fecha}\n"
                    f"   - Entrega Estimada: {entrega_est}\n"
                    f"   - Productos en este pedido:"
                )
                
                lineas_reporte.append(info_pedido)
                
                
                sql_detalles = """
                    SELECT 
                        p.nombre_producto,
                        pv.color,
                        pv.talla,
                        dp.cantidad,
                        dp.precio_unitario
                    FROM detalle_pedido dp
                    INNER JOIN producto_variante pv ON dp.id_variante = pv.id_variante
                    INNER JOIN producto p ON pv.id_producto = p.id_producto
                    WHERE dp.id_pedido = %s
                """
                
                cursor.execute(sql_detalles, (p['id_pedido'],))
                detalles = cursor.fetchall()
                
                if detalles:
                    for d in detalles:
                        lineas_reporte.append(
                            f"     • {d['nombre_producto']} (Color: {d['color']}, Talla: {d['talla']}) x{d['cantidad']} u. [Precio unitario: S/. {d['precio_unitario']}]"
                        )
                else:
                    lineas_reporte.append("     • No se encontraron detalles de productos.")
                
                lineas_reporte.append("-" * 50)
                
            return "\n".join(lineas_reporte)
            
    except Exception as e:
        print(f"🚨 Error al leer el historial completo del usuario {user_id}: {e}")
        return "No se pudo cargar el historial detallado de tus pedidos por un problema técnico."
    finally:
        if connection:
            connection.close()

def obtener_perfil_usuario(user_id: int):
    """
    Trae los datos de perfil del usuario logueado para que Alessia sepa con quién habla.
    """
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = """
                SELECT 
                    u.nombres, 
                    u.apellidos, 
                    u.correo, 
                    u.telefono, 
                    u.numero_documento,
                    td.nombre_tipo_documento
                FROM usuario u
                LEFT JOIN tipo_documento td ON u.id_tipo_documento = td.id_tipo_documento
                WHERE u.id_usuario = %s
            """
            cursor.execute(sql, (user_id,))
            usuario = cursor.fetchone()
            
            if not usuario:
                return "Datos de cliente: Usuario no identificado o visitante anónimo."
            
            # Formateamos el perfil de forma clara para el prompt
            perfil = (
                f"CLIENTE ACTUALMENTE LOGUEADO:\n"
                f"- Nombre Completo: {usuario['nombres']} {usuario['apellidos']}\n"
                f"- Correo Electrónico: {usuario['correo']}\n"
                f"- Teléfono de Contacto: {usuario['telefono'] or 'No registrado'}\n"
                f"- Documento de Identidad: {usuario['nombre_tipo_documento'] or 'Documento'} N° {usuario['numero_documento'] or 'No registrado'}"
            )
            return perfil
            
    except Exception as e:
        print(f"🚨 Error al leer perfil del usuario {user_id}: {e}")
        return "Datos de cliente: No disponibles por error técnico."
    finally:
        if connection:
            connection.close()