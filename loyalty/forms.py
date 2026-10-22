from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, Program, Product
class SignupForm(UserCreationForm):
    class Meta:
        model=User
        fields=['first_name','email']
        labels={'first_name':'Prénom','email':'Adresse e-mail'}
    def clean_email(self):
        email=self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email=email).exists(): raise forms.ValidationError('Cette adresse possède déjà un compte. Connecte-toi ou réinitialise ton mot de passe.')
        return email
class LoginForm(AuthenticationForm):
    def clean_username(self): return self.cleaned_data['username'].strip().lower()
class ProgramForm(forms.ModelForm):
    class Meta:
        model=Program
        fields=['title','mode','threshold','reward','products','stamp_days','reward_days']
        labels={'title':'Nom du programme','mode':'Gain des tampons','threshold':'Tampons nécessaires','reward':'Récompense (décris précisément l’offre)','products':'Produits éligibles','stamp_days':'Validité d’une carte en jours (0 = illimitée)','reward_days':'Validité d’une récompense en jours (0 = illimitée)'}
        widgets={'products':forms.CheckboxSelectMultiple}
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw); self.fields['products'].queryset=Product.objects.filter(active=True)
class SaleForm(forms.Form):
    request_id=forms.UUIDField(widget=forms.HiddenInput)
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        for p in Product.objects.filter(active=True):
            self.fields[f'product_{p.pk}']=forms.IntegerField(label=p.name,min_value=0,max_value=100,initial=0)
    def lines(self): return {k.removeprefix('product_'):v for k,v in self.cleaned_data.items() if k.startswith('product_') and v}
class CodeForm(SaleForm):
    recipient=forms.EmailField(label='E-mail du client (facultatif)',required=False)
    send_email=forms.BooleanField(label='Envoyer le lien par e-mail',required=False)
    def clean(self):
        data=super().clean()
        if data.get('send_email') and not data.get('recipient'): self.add_error('recipient','Indique l’adresse du client.')
        return data
