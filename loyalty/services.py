"""Toutes les mutations métier sont atomiques, y compris les doubles validations."""
import hashlib, secrets
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import Card, Program, Purchase, Reward, Claim, Shop, Product
class BusinessError(ValueError): pass
def current_program():
    program = Program.objects.first()
    if not program: raise BusinessError('Le programme sera bientôt disponible.')
    return program
def deadline(days): return timezone.now()+timedelta(days=days) if days else None
def digest(code): return hashlib.sha256(code.strip().upper().replace('-','').encode()).hexdigest()
def enabled():
    if not Shop.objects.get_or_create(pk=1)[0].enabled:
        raise BusinessError('Le programme est momentanément suspendu.')
def open_card(user):
    card = Card.objects.filter(user=user,closed=False).first()
    if card and card.expires_at and card.expires_at <= timezone.now():
        card.closed=True; card.save(update_fields=['closed']); card=None
    if not card: card=Card.objects.create(user=user,program=current_program())
    elif card.balance==0 and card.program_id != current_program().pk:
        card.program=current_program();card.save(update_fields=['program'])
    return card
def validate_lines(lines):
    if not isinstance(lines,dict) or not lines: raise BusinessError('Choisis au moins un produit.')
    total=0; clean={}
    for pk,qty in lines.items():
        if type(qty) is not int or not 0 < qty <= 100: raise BusinessError('Quantité invalide.')
        if not Product.objects.filter(pk=pk,active=True).exists(): raise BusinessError('Produit indisponible.')
        total+=qty; clean[str(pk)]=qty
    if total>100: raise BusinessError('Maximum 100 produits par achat.')
    return clean
@transaction.atomic
def credit(user,lines,actor,request_id):
    previous=Purchase.objects.filter(pk=request_id).first()
    if previous:
        if previous.user_id != user.pk: raise BusinessError('Identifiant de validation déjà utilisé.')
        return previous
    enabled()
    if not user.verified: raise BusinessError('Le client doit confirmer son adresse e-mail.')
    lines=validate_lines(lines); card=open_card(user)
    before={'id':card.pk,'balance':card.balance,'expires_at':card.expires_at.isoformat() if card.expires_at else None}
    purchase=Purchase.objects.create(id=request_id,user=user,actor=actor,lines=lines,before=before)
    # Le mode est fixé au début de l'achat ; les achats suivants utilisent le mode de la nouvelle carte.
    sale_program=card.program
    mode=sale_program.mode
    eligible=set(card.program.products.values_list('id',flat=True))
    units=[int(pk) for pk,qty in lines.items() for _ in range(qty)]
    if mode=='visit': units=[next((pk for pk in units if pk in eligible),None)]
    for pk in units:
        if pk is None: continue
        if mode=='item' and not card.program.products.filter(pk=pk).exists(): continue
        if card.balance==0: card.expires_at=deadline(card.program.stamp_days)
        card.balance+=1; purchase.stamps+=1
        if card.balance>=card.program.threshold:
            Reward.objects.create(user=user,purchase=purchase,label=card.program.reward,expires_at=deadline(card.program.reward_days))
            card.closed=True; card.save()
            card=Card.objects.create(user=user,program=sale_program)
        else: card.save()
    if not purchase.stamps: raise BusinessError('Aucun produit éligible sur la carte actuelle.')
    if card.balance==0 and card.program_id != current_program().pk:
        card.program=current_program(); card.save(update_fields=['program'])
    purchase.after_card=card; purchase.save(); return purchase
@transaction.atomic
def create_claim(lines,actor,recipient='',request_id=None):
    enabled(); lines=validate_lines(lines)
    if request_id is not None and Claim.objects.filter(request_id=request_id).exists():
        raise BusinessError('Ce formulaire a déjà été utilisé. Recharge la page pour créer un autre code.')
    raw=secrets.token_hex(10).upper()
    claim=Claim.objects.create(digest=digest(raw),lines=lines,actor=actor,recipient=recipient.strip().lower(),expires_at=deadline(30),request_id=request_id or __import__('uuid').uuid4())
    return claim, '-'.join(raw[i:i+5] for i in range(0,len(raw),5))
@transaction.atomic
def redeem_claim(code,user):
    claim=Claim.objects.filter(digest=digest(code)).first()
    if not claim or claim.revoked or claim.purchase_id or claim.expires_at<=timezone.now():
        raise BusinessError('Code invalide, expiré ou déjà utilisé.')
    if claim.recipient and claim.recipient != user.email:
        raise BusinessError('Ce code est réservé à une autre adresse e-mail.')
    import uuid
    purchase=credit(user,claim.lines,claim.actor,uuid.uuid4())
    claim.purchase=purchase; claim.save(update_fields=['purchase']); return purchase
@transaction.atomic
def use_reward(reward_id,actor):
    reward=Reward.objects.get(pk=reward_id)
    if reward.used_at or reward.revoked or (reward.expires_at and reward.expires_at<=timezone.now()):
        raise BusinessError('Cette récompense n’est plus disponible.')
    reward.used_at=timezone.now(); reward.used_by=actor; reward.save()
@transaction.atomic
def cancel_purchase(purchase_id,actor,reason):
    from datetime import datetime
    p=Purchase.objects.get(pk=purchase_id)
    if p.cancelled_at: raise BusinessError('Achat déjà annulé.')
    latest=Purchase.objects.filter(user=p.user,cancelled_at=None).order_by('-created_at').first()
    if latest.pk != p.pk: raise BusinessError('Annule d’abord les achats plus récents de ce client.')
    if p.reward_set.filter(used_at__isnull=False).exists(): raise BusinessError('Une récompense liée à cet achat a déjà été utilisée.')
    active=Card.objects.filter(user=p.user,closed=False).first()
    if not active or active.pk!=p.after_card_id: raise BusinessError('La carte a changé ou expiré : annulation automatique impossible.')
    if not reason.strip(): raise BusinessError('Indique le motif de l’annulation.')
    p.reward_set.update(revoked=True)
    Card.objects.filter(user=p.user,pk__gt=p.before['id']).update(closed=True)
    old=Card.objects.get(pk=p.before['id'])
    old.closed=False; old.balance=p.before['balance']
    old.expires_at=datetime.fromisoformat(p.before['expires_at']) if p.before['expires_at'] else None
    old.save()
    p.cancelled_at=timezone.now(); p.cancelled_by=actor; p.cancel_reason=reason[:200]; p.save()
    # Un code d'achat annulé reste consommé, pour empêcher sa réutilisation.
