from django.urls import path
from django.contrib.auth import views as auth
from loyalty import views
from loyalty.forms import LoginForm
urlpatterns = [
 path('',views.home,name='home'),
 path('inscription/',views.signup,name='signup'),
 path('confirmer/<str:token>/',views.verify,name='verify'),
 path('renvoyer-confirmation/',views.resend_verification,name='resend'),
 path('connexion/',views.MercierLoginView.as_view(template_name='registration/login.html',authentication_form=LoginForm,redirect_authenticated_user=True),name='login'),
 path('deconnexion/',auth.LogoutView.as_view(),name='logout'),
 path('mot-de-passe/',auth.PasswordResetView.as_view(template_name='registration/password_reset_form.html',email_template_name='registration/password_reset_email.txt',subject_template_name='registration/password_reset_subject.txt',success_url='/mot-de-passe/envoye/'),name='password_reset'),
 path('mot-de-passe/envoye/',auth.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'),name='password_reset_done'),
 path('mot-de-passe/reinitialiser/<uidb64>/<token>/',auth.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html',success_url='/mot-de-passe/termine/'),name='password_reset_confirm'),
 path('mot-de-passe/termine/',auth.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'),name='password_reset_complete'),
 path('carte/',views.dashboard,name='dashboard'),
 path('carte/qr.png',views.qr_png,name='qr'),
 path('reclamer/',views.claim,name='claim'),
 path('confidentialite/',views.privacy,name='privacy'),
 path('sante/',views.health,name='health'),
 path('atelier/',views.staff_home,name='staff'),
 path('atelier/clients/',views.customers,name='customers'),
 path('atelier/programme/',views.program,name='program'),
 path('atelier/produits/',views.products,name='products'),
 path('atelier/client/',views.lookup,name='lookup'),
 path('atelier/client/<uuid:card_id>/',views.customer,name='customer'),
 path('atelier/client/<uuid:card_id>/achat/',views.sale,name='sale'),
 path('atelier/codes/',views.codes,name='codes'),
 path('atelier/recompense/<int:pk>/utiliser/',views.redeem,name='redeem'),
 path('atelier/code/<int:pk>/revoquer/',views.revoke_code,name='revoke_code'),
 path('atelier/achat/<uuid:pk>/annuler/',views.cancel,name='cancel'),
]
