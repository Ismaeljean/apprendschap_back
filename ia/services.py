# ia/services.py
import ollama
from cours.models import Chapitre
import logging

# Configurer le logger
logger = logging.getLogger(__name__)

def poser_question_a_l_ia(question, contexte_chapitre=None):
    """
    Pose une question à l'IA via Ollama avec gemma2:2b.
    Inclut le contexte du chapitre si fourni.
    """
    logger.debug(f"Service IA appelé avec question: {question}, contexte_chapitre: {contexte_chapitre}")

    try:
        # Construire le prompt
        prompt = question
        if contexte_chapitre:
            try:
                chapitre = Chapitre.objects.get(id=contexte_chapitre)
                contexte = f"Contexte du chapitre '{chapitre.titre}' : {chapitre.description}\nQuestion : {question}"
                prompt = contexte
                logger.debug(f"Contexte ajouté au prompt: {prompt}")
            except Chapitre.DoesNotExist:
                logger.warning(f"Chapitre avec ID {contexte_chapitre} non trouvé")
                return {"error": f"Chapitre avec ID {contexte_chapitre} non trouvé"}

        # Appeler Ollama avec gemma2:2b (paramètres simples et compatibles)
        response = ollama.chat(
            model="gemma2:2b",
            messages=[
                {"role": "system", "content": "Tu es un assistant pédagogique français. Réponds de manière claire et concise."},
                {"role": "user", "content": prompt}
            ],
            options={
                "temperature": 0.3,
                "top_p": 0.8,
                "num_ctx": 1024,
                "num_thread": 4
            }
        )
        logger.debug(f"Réponse d'Ollama: {response['message']['content']}")
        return response["message"]["content"]

    except Exception as e:
        logger.error(f"Erreur lors de l'appel à Ollama: {str(e)}")
        return {"error": f"Erreur lors de la communication avec l'IA: {str(e)}"}