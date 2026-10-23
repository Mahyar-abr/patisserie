"""Vérifier la configuration SMTP et envoyer un message de diagnostic."""
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


class Command(BaseCommand):
    help = 'Teste l’envoi SMTP depuis le conteneur sans afficher les identifiants.'

    def add_arguments(self, parser):
        parser.add_argument('--to', required=True, help='Adresse qui doit recevoir le test')

    def handle(self, *args, **options):
        recipient = options['to'].strip()
        try:
            validate_email(recipient)
        except ValidationError as exc:
            raise CommandError('Adresse destinataire invalide.') from exc
        if settings.DEBUG:
            raise CommandError('DEBUG=1 : le backend console ne teste pas le SMTP réel.')
        if not settings.EMAIL_HOST:
            raise CommandError('Configuration SMTP incomplète : EMAIL_HOST est obligatoire.')
        if settings.EMAIL_USE_TLS and settings.EMAIL_USE_SSL:
            raise CommandError('EMAIL_USE_TLS et EMAIL_USE_SSL ne peuvent pas être activés ensemble.')
        self.stdout.write(f'Serveur SMTP : {settings.EMAIL_HOST}:{settings.EMAIL_PORT} (aucun mot de passe affiché).')
        try:
            sent = send_mail(
                'Test SMTP Mercier',
                'Ceci est un test du service de messagerie Mercier. Aucune action n’est nécessaire.',
                settings.DEFAULT_FROM_EMAIL,
                [recipient],
                fail_silently=False,
            )
        except Exception as exc:
            # Expose the type to local SSH operator, but avoid leaking SMTP passwords.
            raise CommandError(f'Échec SMTP ({type(exc).__name__}). Consulter les logs locaux et la configuration du fournisseur.') from exc
        if sent != 1:
            raise CommandError('Le serveur SMTP n’a pas accepté le message (0 message envoyé).')
        self.stdout.write(self.style.SUCCESS('Le serveur SMTP a accepté le message. Vérifie sa réception et le dossier spam.'))
