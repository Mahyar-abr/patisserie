import hashlib
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from .models import RateBucket
class RateLimitMiddleware:
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        protected=['/connexion/','/inscription/','/mot-de-passe/','/reclamer/','/renvoyer-confirmation/']
        if request.method=='POST' and any(request.path.startswith(p) for p in protected):
            ip=request.META.get('REMOTE_ADDR','unknown')
            if settings.TRUST_PROXY_IP: ip=request.META.get('HTTP_X_FORWARDED_FOR',ip).split(',')[-1].strip()
            key=hashlib.sha256((ip+request.path).encode()).hexdigest()
            now=timezone.now()
            with transaction.atomic():
                bucket,_=RateBucket.objects.get_or_create(key=key,defaults={'expires_at':now+timedelta(minutes=15)})
                if bucket.expires_at<=now: bucket.count=0; bucket.expires_at=now+timedelta(minutes=15)
                bucket.count+=1; bucket.save()
                limited=bucket.count>20
            if limited:
                response=HttpResponse('Trop de tentatives. Réessaie dans 15 minutes.',status=429)
                response['Retry-After']='900'; return response
        return self.get_response(request)
class PrivateMiddleware:
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        response=self.get_response(request)
        response['Cache-Control']='no-store'
        response['Permissions-Policy']='camera=(self), microphone=(), geolocation=()'
        response['Content-Security-Policy']="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response
