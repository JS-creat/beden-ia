import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Importamos las tres funciones desde tu base de datos
from database import obtener_catalogo_existencias, obtener_pedidos_usuario_completo, obtener_perfil_usuario

load_dotenv()

app = FastAPI(
    title="B-EDEN AI Chatbot Service",
    description="Microservicio en Python para el control de la asistente Alessia",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("🚨 ERROR: No se encontró la GEMINI_API_KEY en el archivo .env")

client = genai.Client(api_key=api_key)

# DICCIONARIO EN MEMORIA PARA EL HISTORIAL
historiales_chat = {}

class ChatRequest(BaseModel):
    user_id: int
    message: str

SYSTEM_INSTRUCTION_BASE = """
Eres Alessia, la asistente IA virtual exclusiva de la tienda de ropa B-EDEN.
Tu objetivo es atender a los clientes de forma breve, clara, amigable y sumamente profesional.

INFORMACIÓN CORPORATIVA DE B-EDEN (Usa estos datos fijos para responder sobre la empresa):
- Tienda Física / Ubicación Principal: Jr. Bolognesi N° 908, Concepción, Junin, Perú.
- Horario de Atención: Lunes a Sábado de 10:00 AM a 8:00 PM. Domingos y feriados no hay atención presencial, pero la web recibe pedidos 24/7.
- Sitio Web Oficial: www.bedenb.com (Aquí pueden registrarse, ver fotos de la galería completa y procesar su carrito de compras)Tambien hacemos envios por Agencia no a domicilio.
- Redes Sociales Oficiales:
  * Instagram: @b.eden_premium
  * Facebook: B-EDEN - Concepción
  * TikTok: @B-EDEN
- Métodos de Contacto Soporte/Reclamos: WhatsApp de atención al cliente al número 960247195.

REGLAS ESTRICTAS DE SEGURIDAD Y COMPORTAMIENTO:
1. SOLO respondes preguntas relacionadas con la tienda B-EDEN, su información corporativa, su catálogo de ropa disponible, horarios, compras o envíos.
2. Si el usuario te pregunta sobre CUALQUIER otro tema ajeno al negocio (ej. tareas escolares, recetas de cocina, fútbol, política, chistes, etc.), debes responder amablemente: "Lo siento, como asistente virtual de B-EDEN solo puedo ayudarte con consultas sobre nuestra tienda, información institucional y catálogo de ropa. ¿En qué puedo ayudarte hoy?"
3. Nunca inventes información, productos ni existencias. Guíate ÚNICAMENTE por el inventario real en tiempo real que se te proporciona abajo.
4. MUY IMPORTANTE: Cuando un usuario te pida recomendaciones de ropa para un género específico (ej. "Ropa para mujer" o "Prendas de hombre"), debes filtrar mentalmente y recomendar ÚNICAMENTE los productos que coincidan con el campo "Para: [Género]" del inventario. No mezcles prendas masculinas en solicitudes femeninas ni viceversa.
5. Si un caso es muy complejo o el cliente tiene problemas serios con un pago o pedido, sugiérele contactar al soporte al número de WhatsApp 960247195.

INVENTARIO REAL DE LA TIENDA EN TIEMPO REAL (Usa estos datos exactos para responder y recomendar):
"""

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        uid = request.user_id
        
        # 1. Traer el inventario fresco desde tu base de datos real (con género y categoría)
        inventario_fresco = obtener_catalogo_existencias()
        
        # 2. Traer el historial completo y detallado de pedidos de ESTE usuario específico
        historial_pedidos_usuario = obtener_pedidos_usuario_completo(uid)
        
        # 3. Traer los datos personales del usuario actual desde la BD
        perfil_cliente = obtener_perfil_usuario(uid)
        
        # 4. Fusionar todo el contexto (Perfil + Pedidos) al System Prompt
        contexto_dinamico = f"\n\n{perfil_cliente}\n\nHISTORIAL DE COMPRAS DETALLADO DEL CLIENTE QUE TE ESTÁ HABLANDO EN ESTE MOMENTO:\n{historial_pedidos_usuario}"
        system_instruction_completo = f"{SYSTEM_INSTRUCTION_BASE}\n{inventario_fresco}{contexto_dinamico}"
        
        # 5. Manejo de Historial (Memoria del Chat por usuario)
        if uid not in historiales_chat:
            historiales_chat[uid] = []
            
        # Añadir el mensaje nuevo del usuario al historial
        historiales_chat[uid].append(types.Content(role="user", parts=[types.Part.from_text(text=request.message)]))
        
        # Mantener solo los últimos 10 mensajes
        if len(historiales_chat[uid]) > 10:
            historiales_chat[uid] = historiales_chat[uid][-10:]

        # 6. Llamada limpia a Gemini pasándole TODO el historial acumulado
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=historiales_chat[uid],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction_completo,
                temperature=0.2, # Temperatura baja para máxima precisión
            )
        )
        
        ai_message = response.text if response.text else "Lo siento, no pude procesar tu solicitud."
        
        # 7. Guardar la respuesta de la IA en el historial
        historiales_chat[uid].append(types.Content(role="model", parts=[types.Part.from_text(text=ai_message)]))
        
        return {
            "success": True,
            "message": ai_message,
            "ai_response": ai_message
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": "Hola, en este momento no puedo responder tus mensajes. Por favor, escribe tu consulta de nuevo en unos segundos.",
            "error_log": str(e)
        }

@app.get("/")
def read_root():
    return {"status": "online", "service": "B-EDEN AI Brain"}