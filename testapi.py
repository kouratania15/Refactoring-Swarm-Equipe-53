import os
from dotenv import load_dotenv
import google.generativeai as genai

# Charger les variables d'environnements
load_dotenv()

# Récupérer la clé
api_key = os.getenv("GOOGLE_API_KEY")

print("="*60)
print("🔍 TEST DE LA CLÉ API GEMINI")
print("="*60)

# Vérifier que la clé existe
if not api_key:
    print("❌ ERREUR : Aucune clé trouvée dans .env")
    print("💡 Vérifiez que le fichier .env contient : GOOGLE_API_KEY=votre_clé")
    exit(1)

print(f"✅ Clé trouvée : {api_key[:20]}...{api_key[-5:]}")
print()

# Configurer l'API
try:
    genai.configure(api_key=api_key)
    print("✅ API configurée avec succès")
except Exception as e:
    print(f"❌ Erreur de configuration : {e}")
    exit(1)

# Lister les modèles disponibles
print("\n" + "="*60)
print("📋 MODÈLES DISPONIBLES AVEC VOTRE CLÉ")
print("="*60)

try:
    models_found = False
    for model in genai.list_models():
        if 'generateContent' in model.supported_generation_methods:
            print(f"✅ {model.name}")
            models_found = True
    
    if not models_found:
        print("⚠️  Aucun modèle trouvé (clé peut-être invalide)")
except Exception as e:
    print(f"❌ Erreur lors de la liste des modèles : {e}")
    exit(1)

# Tester un appel simple
print("\n" + "="*60)
print("🧪 TEST D'APPEL API (gemini-2.5-flash-latest)")
print("="*60)

try:
    model = genai.GenerativeModel("gemini-2.5-flash-latest")
    response = model.generate_content("Réponds juste 'API OK' si tu fonctionnes")
    print(f"✅ Réponse du modèle : {response.text}")
    print("\n🎉 TOUT FONCTIONNE ! Votre clé est valide.")
except Exception as e:
    print(f"❌ Erreur lors de l'appel : {e}")
    print("\n💡 Essayez de créer une nouvelle clé sur Google AI Studio")

print("="*60)