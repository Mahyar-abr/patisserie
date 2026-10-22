from django.core.management.base import BaseCommand
from loyalty.models import Product, Program, Shop
class Command(BaseCommand):
    help='Initialise trois produits provisoires et un programme modifiable.'
    def handle(self,*args,**kwargs):
        Shop.objects.get_or_create(pk=1)
        for name in ['Tiramisu classique','Tiramisu chocolat','Tiramisu spéculoos']:
            Product.objects.get_or_create(name=name)
        if not Program.objects.exists():
            rule=Program.objects.create(title='Les douceurs récompensées',threshold=10,reward='Un tiramisu classique offert')
            rule.products.set(Product.objects.all())
        self.stdout.write(self.style.SUCCESS('Initialisation terminée. Vérifie les noms des produits avec Mercier.'))
