import io, uuid
from functools import wraps
import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.mail import send_mail
from django.db import connection
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth.views import LoginView
from .forms import SignupForm, ProgramForm, SaleForm, CodeForm
from .models import Card, Product, Program, Shop, Purchase, Reward, Claim
from .services import open_card, credit, create_claim, redeem_claim, use_reward, cancel_purchase, BusinessError
User=get_user_model()
def brand(request):
    return {'brand':'Pâtisserie Mercier','contact_email':settings.CONTACT_EMAIL,'identity':settings.BUSINESS_IDENTITY}
def staff_required(fn):
    @login_required
    @wraps(fn)
    def wrapped(request,*args,**kwargs):
        if not request.user.is_staff: raise Http404()
        return fn(request,*args,**kwargs)
    return wrapped

class MercierLoginView(LoginView):
    """Direct staff users to their management area after sign-in."""
    def get_success_url(self):
        if self.request.user.is_staff and not self.get_redirect_url():
            return reverse('staff')
        return super().get_success_url()

def home(request):
    program=Program.objects.first()
    return render(request,'loyalty/home.html',{'program':program,'products':Product.objects.filter(active=True)})
def send_verification(request,user):
    token=signing.dumps({'uid':user.pk,'email':user.email},salt='mercier-verify')
    url=request.build_absolute_uri(reverse('verify',args=[token]))
    send_mail('Confirme ta carte Mercier',f'Bonjour {user.first_name or ""},\n\nPour activer ta carte, ouvre ce lien dans les 24 heures :\n{url}\n\nSi tu n’as pas demandé cette inscription, ignore ce message.',settings.DEFAULT_FROM_EMAIL,[user.email],fail_silently=False)
def signup(request):
    if request.user.is_authenticated: return redirect('dashboard')
    form=SignupForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        user=form.save()
        login(request,user)
        try: send_verification(request,user); messages.success(request,'Un lien de confirmation vient de t’être envoyé.')
        except Exception: messages.warning(request,'Ton compte a été créé, mais le courriel n’a pas pu partir. Réessaie plus tard ou contacte Mercier.')
        return redirect('dashboard')
    return render(request,'loyalty/signup.html',{'form':form})
def verify(request,token):
    try: data=signing.loads(token,salt='mercier-verify',max_age=86400)
    except (signing.BadSignature,signing.SignatureExpired):
        messages.error(request,'Lien invalide ou expiré. Demande un nouvel e-mail de confirmation.'); return redirect('resend')
    user=get_object_or_404(User,pk=data['uid'],email=data['email'])
    if not user.verified: user.verified=True; user.save(update_fields=['verified'])
    messages.success(request,'Ton adresse est confirmée. Ta carte est active !')
    return redirect('dashboard' if request.user.pk==user.pk else 'login')
def resend_verification(request):
    if request.method=='POST':
        email=request.POST.get('email','').strip().lower()
        user=User.objects.filter(email=email,verified=False).first()
        if user:
            try: send_verification(request,user)
            except Exception: pass
        messages.success(request,'Si un compte non confirmé existe, un nouveau lien a été envoyé.')
        return redirect('login')
    return render(request,'loyalty/resend.html')
@login_required
def dashboard(request):
    card=open_card(request.user) if request.user.verified else None
    rewards=Reward.objects.filter(user=request.user,revoked=False).order_by('-id')
    purchases=Purchase.objects.filter(user=request.user).order_by('-created_at')[:12]
    return render(request,'loyalty/dashboard.html',{'card':card,'rewards':rewards,'purchases':purchases,'now':timezone.now(),'stamps':list(range(card.program.threshold)) if card else []})
@login_required
def qr_png(request):
    if not request.user.verified: raise Http404()
    qr=qrcode.QRCode(border=2,box_size=8)
    qr.add_data(str(request.user.card_id)); qr.make(fit=True)
    out=io.BytesIO(); qr.make_image(fill_color='#38211e',back_color='#fffdf7').save(out,format='PNG')
    response=HttpResponse(out.getvalue(),content_type='image/png'); response['Cache-Control']='private, no-store'; return response
@login_required
def claim(request):
    if request.method=='POST':
        try:
            p=redeem_claim(request.POST.get('code',''),request.user)
            messages.success(request,f'Achat enregistré : {p.stamps} tampon(s).'); return redirect('dashboard')
        except BusinessError as exc: messages.error(request,str(exc))
    return render(request,'loyalty/claim.html')
def privacy(request): return render(request,'loyalty/privacy.html')
def health(request):
    try:
        with connection.cursor() as cursor: cursor.execute('SELECT COUNT(*) FROM loyalty_program')
    except Exception: return JsonResponse({'status':'unavailable'},status=503)
    return JsonResponse({'status':'ready'})
@staff_required
def staff_home(request):
    return render(request,'loyalty/staff.html',{'active':Purchase.objects.filter(cancelled_at=None).count(),'pending':Reward.objects.filter(used_at=None,revoked=False).count(),'customers':User.objects.filter(is_staff=False).count(),'recent':Purchase.objects.select_related('user').order_by('-created_at')[:12],'shop':Shop.objects.get_or_create(pk=1)[0]})
@staff_required
def program(request):
    shop=Shop.objects.get_or_create(pk=1)[0]
    current=Program.objects.first()
    if request.method=='POST' and request.POST.get('action')=='toggle':
        shop.enabled=not shop.enabled; shop.save(update_fields=['enabled']); messages.success(request,'Programme activé.' if shop.enabled else 'Programme suspendu.'); return redirect('program')
    form=ProgramForm(request.POST or None,initial={'title':current.title if current else 'Les douceurs récompensées','mode':current.mode if current else 'item','threshold':current.threshold if current else 10,'reward':current.reward if current else 'Un tiramisu offert','stamp_days':current.stamp_days if current else 0,'reward_days':current.reward_days if current else 0,'products':current.products.all() if current else Product.objects.filter(active=True)})
    if request.method=='POST' and form.is_valid() and request.POST.get('action')=='save':
        rule=form.save()
        messages.success(request,'Nouvelle version publiée. Les cartes commencées gardent leur règle ; les nouvelles cartes utilisent cette version.')
        return redirect('program')
    return render(request,'loyalty/program.html',{'form':form,'current':current,'shop':shop,'history':Program.objects.all()[:8]})
@staff_required
def products(request):
    if request.method=='POST':
        action=request.POST.get('action','create')
        name=request.POST.get('name','').strip()
        if action in ('rename','toggle'):
            product=get_object_or_404(Product,pk=request.POST.get('product_id'))
            if action=='toggle':
                product.active=not product.active; product.save(update_fields=['active'])
                messages.success(request,'Produit activé.' if product.active else 'Produit désactivé.')
            elif not name or len(name)>80 or Product.objects.filter(name__iexact=name).exclude(pk=product.pk).exists():
                messages.error(request,'Nom invalide ou déjà utilisé.')
            else:
                product.name=name; product.save(update_fields=['name']); messages.success(request,'Nom modifié.')
        elif action=='create':
            if not name or len(name)>80 or Product.objects.filter(name__iexact=name).exists(): messages.error(request,'Nom invalide ou déjà utilisé (1 à 80 caractères).')
            else: Product.objects.create(name=name); messages.success(request,'Produit ajouté.')
        return redirect('products')
    return render(request,'loyalty/products.html',{'products':Product.objects.all()})
@staff_required
def lookup(request):
    q=request.GET.get('q','').strip()
    if q:
        user=User.objects.filter(email__iexact=q).first()
        if not user:
            try: user=User.objects.filter(card_id=uuid.UUID(q)).first()
            except ValueError: pass
        if user and user.verified: return redirect('customer',card_id=user.card_id)
        messages.error(request,'Carte introuvable ou adresse non confirmée.')
    return render(request,'loyalty/lookup.html')
@staff_required
def customer(request,card_id):
    user=get_object_or_404(User,card_id=card_id,verified=True)
    card=open_card(user)
    return render(request,'loyalty/customer.html',{'customer':user,'card':card,'rewards':Reward.objects.filter(user=user,revoked=False).order_by('-id'),'purchases':Purchase.objects.filter(user=user).order_by('-created_at')[:20],'now':timezone.now()})
@staff_required
def sale(request,card_id):
    user=get_object_or_404(User,card_id=card_id,verified=True)
    form=SaleForm(request.POST or None,initial={'request_id':uuid.uuid4()})
    if request.method=='POST' and form.is_valid():
        try:
            p=credit(user,form.lines(),request.user,form.cleaned_data['request_id'])
            messages.success(request,f'Achat validé : {p.stamps} tampon(s).'); return redirect('customer',card_id=card_id)
        except BusinessError as exc: messages.error(request,str(exc))
    return render(request,'loyalty/sale.html',{'customer':user,'form':form})
@staff_required
def codes(request):
    form=CodeForm(request.POST or None,initial={'request_id':uuid.uuid4()})
    code=None; url=None
    if request.method=='POST' and form.is_valid():
        try:
            rec=form.cleaned_data['recipient']
            obj,code=create_claim(form.lines(),request.user,rec,form.cleaned_data['request_id'])
            url=request.build_absolute_uri(reverse('claim'))+'?code='+code
            if form.cleaned_data['send_email']:
                try:
                    send_mail('Ton achat chez Mercier',f'Bonjour,\n\nPour ajouter ton achat à ta carte, connecte-toi puis ouvre ce lien :\n{url}\n\nCe code est personnel, utilisable une seule fois et valable 30 jours.\n\nPâtisserie Mercier',settings.DEFAULT_FROM_EMAIL,[rec])
                    obj.emailed_at=timezone.now();obj.save(update_fields=['emailed_at'])
                    messages.success(request,'Code créé et e-mail envoyé.')
                except Exception: messages.warning(request,'Code créé, mais l’e-mail n’a pas pu être envoyé. Copie le lien ci-dessous.')
            else: messages.success(request,'Code créé. Copie-le maintenant : il ne sera plus affiché.')
        except BusinessError as exc: messages.error(request,str(exc))
    return render(request,'loyalty/codes.html',{'form':form,'code':code,'url':url,'recent':Claim.objects.order_by('-created_at')[:12],'now':timezone.now()})
@staff_required
@require_POST
def revoke_code(request,pk):
    obj=get_object_or_404(Claim,pk=pk)
    if obj.purchase_id: messages.error(request,'Un code déjà utilisé ne peut pas être révoqué.')
    else:
        obj.revoked=True;obj.save(update_fields=['revoked']);messages.success(request,'Code révoqué.')
    return redirect('codes')
@staff_required
@require_POST
def redeem(request,pk):
    reward=get_object_or_404(Reward,pk=pk)
    try: use_reward(pk,request.user); messages.success(request,'Récompense remise au client.')
    except BusinessError as exc: messages.error(request,str(exc))
    return redirect('customer',card_id=reward.user.card_id)
@staff_required
@require_POST
def cancel(request,pk):
    purchase=get_object_or_404(Purchase,pk=pk)
    try: cancel_purchase(pk,request.user,request.POST.get('reason','')); messages.success(request,'Achat annulé et carte rétablie.')
    except BusinessError as exc: messages.error(request,str(exc))
    return redirect('customer',card_id=purchase.user.card_id)
