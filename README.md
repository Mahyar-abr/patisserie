# Mercier — carte de fidélité pour pâtisserie

Application web légère en français, pensée pour les téléphones et pour un petit serveur Oracle. Les clients créent leur compte, confirment leur adresse e-mail et présentent leur QR code en boutique. Mercier valide l'achat depuis son espace de gestion. Pour une vente à distance, elle peut créer un code à usage unique et envoyer un lien par e-mail. Aucun paiement en ligne.

## Ce qui fonctionne

- Carte personnelle avec QR code, progression, historique et récompenses.
- Inscription, confirmation d'e-mail, connexion et récupération de mot de passe.
- Espace Mercier protégé par le rôle « staff » : lecture QR sur les navigateurs compatibles, recherche par adresse e-mail ou identifiant, saisie des quantités, remise des récompenses, correction d'un dernier achat.
- Codes d'achat aléatoires, utilisables une seule fois, valables 30 jours, réservables à une adresse e-mail ; envoi par SMTP, révocation possible.
- Programme configurable : gain par tiramisu ou par achat, seuil entre 1 et 100 tampons, récompense libre, produits éligibles, expiration facultative des cartes et des récompenses, suspension/réactivation.
- Historique des versions du programme. Une carte avec des tampons conserve sa règle jusqu'à sa prochaine récompense ou expiration. Une carte vide adopte la dernière règle. Tous les produits d'une même vente sont crédités selon la règle en vigueur sur la carte au début de cette vente. Les récompenses gagnées conservent leur libellé et leur date limite.

**Valeurs de démonstration à personnaliser** : les trois produits (« classique », « chocolat », « spéculoos ») et la règle « 10 tampons = 1 tiramisu classique ». Ce ne sont pas des informations vérifiées auprès de Mercier. Renomme ou désactive les produits provisoires dans l'atelier et publie les vraies règles avant d'ouvrir le site aux clients.

## Architecture

Django 5.2, pages HTML/CSS, un petit script JS pour la caméra, SQLite, Gunicorn et WhiteNoise. Pas de compilation front-end ni de service de paiement. Les écritures d'achat, de code et de récompense utilisent une transaction SQLite ; une validation de vente rejouée avec le même identifiant n'ajoute pas une deuxième fois les tampons. Les codes sont conservés uniquement sous forme d'empreinte SHA-256. Les mots de passe utilisent le hachage de Django. Le QR code contient un identifiant public aléatoire, jamais un droit de crédit : seuls les comptes staff peuvent valider les achats.

## Essayer en local

Python 3.12 recommandé. Depuis le dossier `mercier/` :

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
DEBUG=1 python manage.py migrate
DEBUG=1 python manage.py seed_mercier
DEBUG=1 python manage.py createsuperuser
DEBUG=1 python manage.py runserver
```

Ouvre `http://127.0.0.1:8000/`. L'e-mail de confirmation apparaît dans le terminal en mode local. Le superutilisateur créé a accès à `/atelier/`. Pour une démonstration, crée un compte client séparé et clique le lien de confirmation imprimé par le serveur. La caméra demande HTTPS en production et dépend du navigateur ; la recherche par e-mail reste disponible.

## Déployer sur ton serveur Oracle

Lis [docs/DEPLOIEMENT_ORACLE.md](docs/DEPLOIEMENT_ORACLE.md). Le projet est prévu pour `mercier.arvimah.top`, avec Caddy devant un conteneur exposé uniquement sur `127.0.0.1:8091`. Le site n'a pas été déployé depuis cet espace : il faut renseigner le DNS, l'e-mail SMTP, l'identité/contact de la pâtisserie et les récompenses réelles.

## Utilisation de l'atelier

1. `/atelier/produits/` : renommer/activer/désactiver les produits.
2. `/atelier/programme/` : publier les règles, puis vérifier l'affichage sur une carte client.
3. `/atelier/client/` : lire un QR code ou chercher une carte ; inscrire les quantités et confirmer.
4. `/atelier/codes/` : générer un code ou envoyer le lien. Le code en clair n'est visible qu'une seule fois.
5. Sur la carte client : valider la remise d'une récompense ou annuler le dernier achat si aucune récompense associée n'a été utilisée.

Un code créé avant un changement de règles crédite l'achat **selon la règle de la carte au moment où le client réclame le code**. Si la règle doit impérativement être figée à la date de vente, il faudra ajouter cette option avant l'ouverture publique. Une vente corrigée ne réactive pas son code déjà utilisé.

## Limites connues et décisions avant ouverture

- La lecture caméra exploite `BarcodeDetector` quand le navigateur le prend en charge. Sinon, saisie de l'e-mail ou de l'identifiant de carte.
- L'application ne vérifie pas l'existence d'un paiement ; Mercier doit confirmer la vente elle-même.
- Les dates de validité sont fixées lors de la création de la carte ou de la récompense ; une nouvelle règle n'efface pas les droits acquis.
- SQLite est approprié pour un faible volume sur un seul serveur. Prévoir sauvegardes, surveillance et évolution vers PostgreSQL si le trafic ou le nombre de points de vente augmente.
- La gestion des demandes d'accès, rectification et suppression des données est manuelle pour cette première version. Compléter les informations légales et la durée de conservation avec la pâtisserie avant mise en ligne.

## Tests

```bash
DEBUG=1 python manage.py test loyalty
DEBUG=1 python manage.py check
```

Le jeu de tests couvre inscription/confirmation, pages, contrôle d'accès, achat, changement de règle, code personnel à usage unique, récompense et annulation. Les répertoires `db.sqlite3`, `.env` et `staticfiles/` sont exclus de l'archive livrée.
