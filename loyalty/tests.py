import uuid
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core import mail
from django.core import signing
from django.utils import timezone
from .models import User, Product, Program, Card, Purchase, Reward, Claim, Shop
from .services import credit, redeem_claim, create_claim, cancel_purchase, BusinessError, use_reward

@override_settings(DEBUG=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class LoyaltyFlowTests(TestCase):
    def setUp(self):
        self.staff=User.objects.create_superuser('mercier@example.com','a-long-test-password')
        self.client_user=User.objects.create_user('client@example.com','a-long-test-password',first_name='Camille',verified=True)
        self.product=Product.objects.create(name='Tiramisu maison')
        self.rule=Program.objects.create(mode='item',threshold=2,reward='Un tiramisu offert')
        self.rule.products.add(self.product)

    def test_full_purchase_reward_redemption_and_rule_version(self):
        p=credit(self.client_user,{str(self.product.pk):2},self.staff,uuid.uuid4())
        self.assertEqual(p.stamps,2)
        gift=Reward.objects.get(purchase=p)
        self.assertEqual(gift.label,'Un tiramisu offert')
        self.assertEqual(Card.objects.get(user=self.client_user,closed=False).balance,0)
        newer=Program.objects.create(mode='visit',threshold=3,reward='Une surprise')
        newer.products.add(self.product)
        self.assertEqual(Card.objects.get(user=self.client_user,closed=False).program_id,self.rule.pk)
        credit(self.client_user,{str(self.product.pk):1},self.staff,uuid.uuid4())
        self.assertEqual(Card.objects.get(user=self.client_user,closed=False).balance,1)
        self.assertEqual(Card.objects.get(user=self.client_user,closed=False).program_id,newer.pk)
        use_reward(gift.pk,self.staff)
        with self.assertRaises(BusinessError): use_reward(gift.pk,self.staff)

    def test_claim_single_use_and_recipient(self):
        claim,code=create_claim({str(self.product.pk):1},self.staff,'client@example.com')
        other=User.objects.create_user('autre@example.com','a-long-test-password',verified=True)
        with self.assertRaises(BusinessError): redeem_claim(code,other)
        redeemed=redeem_claim(code,self.client_user)
        self.assertEqual(redeemed.stamps,1)
        with self.assertRaises(BusinessError): redeem_claim(code,self.client_user)
        self.assertEqual(Claim.objects.get(pk=claim.pk).purchase_id,redeemed.pk)

    def test_cancel_latest_restores_card_and_revokes_reward(self):
        p=credit(self.client_user,{str(self.product.pk):2},self.staff,uuid.uuid4())
        cancel_purchase(p.pk,self.staff,'Erreur de saisie')
        self.assertEqual(Card.objects.get(user=self.client_user,closed=False).balance,0)
        self.assertTrue(Reward.objects.get(purchase=p).revoked)
        self.assertIsNotNone(Purchase.objects.get(pk=p.pk).cancelled_at)

    def test_staff_access_and_post_only(self):
        self.client.force_login(self.client_user)
        self.assertEqual(self.client.get(reverse('staff')).status_code,404)
        self.assertEqual(self.client.post(reverse('program'),{'action':'toggle'}).status_code,404)
        self.assertEqual(self.client.get(reverse('redeem',args=[1])).status_code,404)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('staff')).status_code,200)
        self.assertEqual(self.client.get(reverse('program')).status_code,200)
        self.assertEqual(self.client.get(reverse('lookup')).status_code,200)

    def test_registration_confirmation_flow(self):
        response=self.client.post(reverse('signup'),{'first_name':'Léa','email':' LEA@EXAMPLE.COM ','password1':'a-long-test-password','password2':'a-long-test-password'})
        self.assertRedirects(response,reverse('dashboard'))
        user=User.objects.get(email='lea@example.com')
        self.assertFalse(user.verified)
        self.assertEqual(len(mail.outbox),1)
        token=signing.dumps({'uid':user.pk,'email':user.email},salt='mercier-verify')
        self.client.get(reverse('verify',args=[token]))
        user.refresh_from_db()
        self.assertTrue(user.verified)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code,200)

    def test_single_stamp_per_visit_and_code_form_not_reused(self):
        visit=Program.objects.create(mode='visit',threshold=4,reward='Une surprise')
        visit.products.add(self.product)
        sale=credit(self.client_user,{str(self.product.pk):3},self.staff,uuid.uuid4())
        self.assertEqual(sale.stamps,1)
        request_id=uuid.uuid4()
        create_claim({str(self.product.pk):1},self.staff,request_id=request_id)
        with self.assertRaises(BusinessError): create_claim({str(self.product.pk):1},self.staff,request_id=request_id)

    def test_staff_sale_post_replay_only_credits_once(self):
        self.client.force_login(self.staff)
        identifier=uuid.uuid4()
        data={'request_id':str(identifier),f'product_{self.product.pk}':'1'}
        url=reverse('sale',args=[self.client_user.card_id])
        self.assertEqual(self.client.post(url,data).status_code,302)
        self.assertEqual(self.client.post(url,data).status_code,302)
        self.assertEqual(Purchase.objects.filter(user=self.client_user).count(),1)
        self.assertEqual(Card.objects.get(user=self.client_user,closed=False).balance,1)

    def test_pages_render(self):
        for name in ['home','privacy','login','signup']:
            self.assertEqual(self.client.get(reverse(name)).status_code,200)
        self.client.force_login(self.client_user)
        for name in ['dashboard','claim','qr']:
            self.assertEqual(self.client.get(reverse(name)).status_code,200)
        self.client.force_login(self.staff)
        for name in ['staff','program','products','lookup','codes']:
            self.assertEqual(self.client.get(reverse(name)).status_code,200)
        self.assertEqual(self.client.get(reverse('customer',args=[self.client_user.card_id])).status_code,200)
        self.assertEqual(self.client.get(reverse('sale',args=[self.client_user.card_id])).status_code,200)
