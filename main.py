import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Importamos tu función de la base de datos
from database import obtener_catalogo_existencias

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

# DICCIONARIO EN MEMORIA PARA EL HISTORIAL (Guarda los últimos mensajes por usuario)
# Nota: Para la sustentación esto es perfecto. En producción se pasaría a Redis o la BD.
historiales_chat = {}

class ChatRequest(BaseModel):
    user_id: int
    message: str

SYSTEM_INSTRUCTION_BASE = """
Eres Alessia, la asistente virtual exclusiva de la tienda de ropa B-EDEN.
Tu objetivo es atender a los clientes de forma breve, clara, amigable y sumamente profesional.

REGLAS ESTRICTAS DE SEGURIDAD Y COMPORTAMIENTO:
1. SOLO respondes preguntas relacionadas con la tienda B-EDEN, su catálogo de ropa disponible, horarios, compras o envíos.
2. Si el usuario te pregunta sobre CUALQUIER otro tema ajeno al negocio (ej. tareas escolares, recetas de cocina, fútbol, política, chistes, etc.), debes responder amablemente: "Lo siento, como asistente virtual de B-EDEN solo puedo ayudarte con consultas sobre nuestra tienda y catálogo de ropa. ¿En qué prenda estás interesado hoy?"
3. Nunca inventes información, productos ni existencias. Guíate ÚNICAMENTE por el inventario real en tiempo real que se te proporciona abajo. Si no está en la lista o no tiene stock, dile cordialmente al cliente que no está disponible por el momento.
4. Si un caso es muy especial o el cliente tiene problemas con un pedido, sugiérele contactar al soporte al número 992387342.

INVENTARIO REAL DE LA TIENDA EN TIEMPO REAL (Usa estos datos exactos para responder):
"""

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        # 1. Traer el inventario fresco desde tu base de datos real
        inventario_fresco = obtener_catalogo_existencias()
        
        # 2. Fusionar las reglas con el stock actual para armar el prompt del sistema
        system_instruction_completo = f"{SYSTEM_INSTRUCTION_BASE}\n{inventario_fresco}"
        
        # 3. Manejo de Historial (Memoria del Chat por usuario)
        uid = request.user_id
        if uid not in historiales_chat:
            historiales_chat[uid] = []
            
        # Añadir el mensaje nuevo del usuario al historial
        historiales_chat[uid].append(types.Content(role="user", parts=[types.Part.from_text(text=request.message)]))
        
        # Mantener solo los últimos 10 mensajes para no saturar la memoria ni gastar tokens de más
        if len(historiales_chat[uid]) > 10:
            historiales_chat[uid] = historiales_chat[uid][-10:]

        # 4. Llamada limpia a Gemini pasándole TODO el historial acumulado
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=historiales_chat[uid],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction_completo,
                temperature=0.2, # Temperatura baja para que sea precisa con los precios y stock
            )
        )
        
        ai_message = response.text if response.text else "Lo siento, no pude procesar tu solicitud."
        
        # 5. Guardar la respuesta de la IA en el historial para que recuerde lo que ella misma dijo
        historiales_chat[uid].append(types.Content(role="model", parts=[types.Part.from_text(text=ai_message)]))
        
        return {
            "success": True,
            "message": ai_message,
            "ai_response": ai_message
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": "Hola, En este momento no puedo responder tus mensajes. Por favor, escribe tu consulta de nuevo en unos segundos.",
            "error_log": str(e)
        }

@app.get("/")
def read_root():
    return {"status": "online", "service": "B-EDEN AI Brain"}