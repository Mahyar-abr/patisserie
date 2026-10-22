import uuid
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MinValueValidator, MaxValueValidator
class UserManager(BaseUserManager):
    use_in_migrations = True
    def create_user(self, email, password=None, **extra):
        if not email: raise ValueError('E-mail obligatoire')
        user = self.model(email=email.strip().lower(), **extra)
        user.set_password(password); user.save(using=self._db); return user
    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True, verified=True)
        return self.create_user(email,password,**extra)
class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    verified = models.BooleanField(default=False)
    card_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()
class Product(models.Model):
    name = models.CharField(max_length=80)
    active = models.BooleanField(default=True)
    def __str__(self): return self.name
class Shop(models.Model):
    enabled = models.BooleanField(default=True)
class Program(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=80, default='Les douceurs récompensées')
    mode = models.CharField(max_length=10, choices=[('item','Par tiramisu'),('visit','Par achat')], default='item')
    threshold = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1),MaxValueValidator(100)])
    reward = models.CharField(max_length=160, default='Un tiramisu classique offert')
    products = models.ManyToManyField(Product)
    stamp_days = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(3650)])
    reward_days = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(3650)])
    class Meta: ordering = ['-id']
class Card(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    program = models.ForeignKey(Program,on_delete=models.PROTECT)
    balance = models.PositiveIntegerField(default=0)
    closed = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['user'],condition=Q(closed=False),name='one_open_card')]
class Purchase(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    actor = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,related_name='sales')
    created_at = models.DateTimeField(auto_now_add=True)
    lines = models.JSONField()
    stamps = models.PositiveIntegerField(default=0)
    before = models.JSONField(default=dict)
    after_card = models.ForeignKey(Card,on_delete=models.SET_NULL,null=True)
    cancelled_at = models.DateTimeField(null=True)
    cancel_reason = models.CharField(max_length=200,blank=True)
    cancelled_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,related_name='cancellations')
class Reward(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    purchase = models.ForeignKey(Purchase,on_delete=models.CASCADE)
    label = models.CharField(max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True)
    used_at = models.DateTimeField(null=True)
    used_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,related_name='redemptions')
    revoked = models.BooleanField(default=False)
class Claim(models.Model):
    request_id = models.UUIDField(default=uuid.uuid4,unique=True,editable=False)
    digest = models.CharField(max_length=64,unique=True)
    lines = models.JSONField()
    recipient = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    actor = models.ForeignKey(User,on_delete=models.SET_NULL,null=True)
    purchase = models.OneToOneField(Purchase,on_delete=models.SET_NULL,null=True)
    revoked = models.BooleanField(default=False)
    emailed_at = models.DateTimeField(null=True)
class RateBucket(models.Model):
    key = models.CharField(max_length=64,primary_key=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()
