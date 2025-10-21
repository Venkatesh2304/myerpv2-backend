from django.db import models
from django.db.models import CharField,IntegerField,OneToOneField,FloatField,ForeignKey,DateField,BooleanField
from django.db.models import Sum,F

class CompanyModel(models.Model):
      company = models.ForeignKey("app.Company",on_delete=models.CASCADE,db_index=True)
      class Meta :
            abstract = True

## Abstract models
class PartyVoucher(models.Model) : 
      inum = CharField(max_length=20)
      party_id  = CharField(max_length=20)
      date = DateField()
      amt = FloatField(null=True)

      def __str__(self) -> str:
            return self.inum

      class Meta : 
            abstract = True 

class GstVoucher(models.Model) : 
      ctin = CharField(max_length=20,null=True,blank=True)
      irn = CharField(max_length=80,null=True,blank=True)
      gst_period = CharField(max_length=12,null=True,blank=True)
    
      class Meta : 
            abstract = True 

## Models For Accounting

class Party(CompanyModel) : 
      code = CharField(max_length=10,db_index=True)
      master_code = CharField(max_length=10,null=True,blank=True)
      name = CharField(max_length=80,null=True,blank=True)
      type = CharField(db_default="shop",max_length=10)
      addr = CharField(max_length=150,blank=True,null=True)
      pincode = IntegerField(blank=True,null=True)
      ctin = CharField(max_length=20,null=True,blank=True)
      phone = CharField(max_length=20,null=True,blank=True)

      def __str__(self) -> str:
            return self.code 
     
      class Meta : 
            verbose_name_plural = 'Party'
            unique_together = ("company","code")

class Stock(CompanyModel) : 
      name = CharField(max_length=20,db_index=True)
      hsn = CharField(max_length=20,null=True)
      desc = CharField(max_length=20,null=True,blank=True)
      rt = FloatField(null=True)
      standard_rate = FloatField(null=True,blank=True)
      def __str__(self) -> str:
            return self.name 
      class Meta : 
            verbose_name_plural = 'Stock'
            unique_together = ("company","name")
      
class Inventory(CompanyModel) : 
      stock_id = models.CharField(max_length=10)
      qty = IntegerField()
      txval = FloatField(blank=True,null=True)
      rt = FloatField(blank=True,null=True)
      bill_id = models.CharField(max_length=20,null=True,blank=True,db_index=True)
      pur_bill_id = models.CharField(max_length=20,null=True,blank=True,db_index=True)
      adj_bill_id = models.CharField(max_length=20,null=True,blank=True,db_index=True)
      # class Meta : 
      #       unique_together = (("stock","bill"),("stock","pur_bill"),("stock","adj_bill"))

class Sales(CompanyModel, PartyVoucher, GstVoucher) :
      discount = FloatField(default=0,db_default=0)
      roundoff = FloatField(default=0,db_default=0)
      type = CharField(max_length=15,db_default="sales",null=True)
      tds = FloatField(default=0,db_default=0)
      tcs = FloatField(default=0,db_default=0)
      class Meta: # type: ignore
        verbose_name_plural = 'Sales'

class Discount(CompanyModel): 
      bill_id = models.CharField(max_length=20)
      sub_type = CharField(max_length=20)
      type = CharField(null=True,blank=True,max_length=20)
      amt =  FloatField(default=0,db_default=0)
      moc = CharField(max_length=30,null=True,blank=True)
      class Meta : 
            # unique_together = ("sub_type","bill_id")
            verbose_name_plural = 'Discount'
        
class Purchase(CompanyModel, PartyVoucher, GstVoucher) : #No txval 
      #txval = FloatField(null=True)
      type = CharField(max_length=15,db_default="purchase",null=True)
      ref = CharField(max_length=15,null=True)
      tds = FloatField(default=0,db_default=0)
      tcs = FloatField(default=0,db_default=0)
      class Meta :  # type: ignore
            verbose_name_plural = 'Purchase'
      
class StockAdjustment(CompanyModel) : 
      inum = CharField(max_length=20)
      date = DateField()
      godown = CharField(max_length=20,null=True)
