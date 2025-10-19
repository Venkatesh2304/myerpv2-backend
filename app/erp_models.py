from django.db import models
from django.db.models import CharField,IntegerField,OneToOneField,FloatField,ForeignKey,DateField,BooleanField
from django.db.models import Sum,F

## Abstract models

class PartyVoucher(models.Model) : 
      inum = CharField(max_length=20,primary_key=True)
      party = ForeignKey("app.Party",on_delete=models.DO_NOTHING,null=True,db_constraint=False)
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

class Party(models.Model) : 
      code = CharField(max_length=10,primary_key=True)
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

class Stock(models.Model) : 
      name = CharField(max_length=20,primary_key=True)
      hsn = CharField(max_length=20,null=True)
      desc = CharField(max_length=20,null=True,blank=True)
      rt = FloatField(null=True)
      standard_rate = FloatField(null=True,blank=True)
      def __str__(self) -> str:
            return self.name 
      class Meta : 
            verbose_name_plural = 'Stock'
      
class Inventory(models.Model) : 
      stock = ForeignKey("app.Stock",on_delete=models.DO_NOTHING,related_name="invs",db_constraint=False) 
      qty = IntegerField()
      txval = FloatField(blank=True,null=True)
      rt = FloatField(blank=True,null=True)
      bill = ForeignKey("app.Sales",on_delete=models.CASCADE,related_name="invs",null=True,blank=True,db_constraint=False)
      pur_bill = ForeignKey("app.Purchase",on_delete=models.CASCADE,related_name="invs",null=True,blank=True,db_constraint=False)
      adj_bill = ForeignKey("app.StockAdjustment",on_delete=models.CASCADE,related_name="invs",null=True,blank=True,db_constraint=False)
      # class Meta : 
      #       unique_together = (("stock","bill"),("stock","pur_bill"),("stock","adj_bill"))

class Sales( PartyVoucher,GstVoucher ) :
      discount = FloatField(default=0,db_default=0)
      roundoff = FloatField(default=0,db_default=0)
      type = CharField(max_length=15,db_default="sales",null=True)
      tds = FloatField(default=0,db_default=0)
      tcs = FloatField(default=0,db_default=0)
      class Meta: # type: ignore
        verbose_name_plural = 'Sales'

class Discount(models.Model): 
      bill = ForeignKey("app.Sales",on_delete=models.CASCADE,related_name="discounts",db_constraint=True)
      sub_type = CharField(max_length=20)
      type = CharField(null=True,blank=True,max_length=20)
      amt =  FloatField(default=0,db_default=0)
      moc = CharField(max_length=30,null=True,blank=True)
      class Meta : 
            unique_together = ("sub_type","bill")
            verbose_name_plural = 'Discount'
        
class Purchase( PartyVoucher , GstVoucher ) : #No txval 
      #txval = FloatField(null=True)
      type = CharField(max_length=15,db_default="purchase",null=True)
      ref = CharField(max_length=15,null=True)
      tds = FloatField(default=0,db_default=0)
      tcs = FloatField(default=0,db_default=0)
      class Meta :  # type: ignore
            verbose_name_plural = 'Purchase'
      
class StockAdjustment(models.Model) : 
      inum = CharField(max_length=20,primary_key=True)
      date = DateField()
      godown = CharField(max_length=20,null=True)
