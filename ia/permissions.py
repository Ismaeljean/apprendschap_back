# ia/permissions.py
from rest_framework import permissions
from django.contrib.auth.models import User
from .models import ConversationIA



class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission personnalisée pour permettre seulement aux propriétaires 
    d'un objet de le modifier.
    """
    
    def has_object_permission(self, request, view, obj):
        # Permissions de lecture pour toutes les requêtes
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Permissions d'écriture seulement pour le propriétaire
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'etudiant'):
            return obj.etudiant == request.user
        elif hasattr(obj, 'owner'):
            return obj.owner == request.user
        
        return False
