from django.db import models,transaction
from django.db.models import CharField,IntegerField,OneToOneField,FloatField,ForeignKey,DateField,BooleanField,CompositePrimaryKey
from django.db.models import Sum,F

from app.fields import decimal_field

class CompanyModel(models.Model):
      company = models.ForeignKey("app.Company",on_delete=models.CASCADE,db_index=True)
      class Meta :
            abstract = True

## Abstract models
class PartyVoucher(models.Model) : 
      inum = CharField(max_length=20)
      party_id  = CharField(max_length=20)
      date = DateField()
      amt = decimal_field(required=True)

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
      code = CharField(max_length=10)  # removed db_index (part of composite PK)
      master_code = CharField(max_length=10,null=True,blank=True)
      name = CharField(max_length=80,null=True,blank=True)
      type = CharField(db_default="shop",max_length=10)
      addr = CharField(max_length=150,blank=True,null=True)
      pincode = IntegerField(blank=True,null=True)
      ctin = CharField(max_length=20,null=True,blank=True)
      phone = CharField(max_length=20,null=True,blank=True)
      pk = CompositePrimaryKey("company", "code")

      def __str__(self) -> str:
            return self.code 
     
      class Meta : 
            verbose_name_plural = 'Party'

class Stock(CompanyModel) : 
      name = CharField(max_length=20)  # removed db_index (part of composite PK)
      hsn = CharField(max_length=20,null=True)
      desc = CharField(max_length=200,null=True,blank=True)
      rt = decimal_field(decimal_places=1)
      standard_rate = decimal_field()
      pk = CompositePrimaryKey("company", "name")
      def __str__(self) -> str:
            return self.name 
      class Meta : 
            verbose_name_plural = 'Stock'
      
class Inventory(CompanyModel) : 
      stock_id = models.CharField(max_length=10)
      qty = IntegerField()
      txval = decimal_field(decimal_places=3)
      rt = decimal_field(decimal_places=1)
      bill_id = models.CharField(max_length=20,null=True,blank=True,db_index=True)
      pur_bill_id = models.CharField(max_length=20,null=True,blank=True,db_index=True)
      adj_bill_id = models.CharField(max_length=20,null=True,blank=True,db_index=True)
      #Create a foriegn object for stock 
      stock = models.ForeignObject(
            "Stock",
            null=True,
            on_delete=models.DO_NOTHING,
            from_fields=("company", "stock_id"),
            to_fields=("company", "name"),
      )
      # Relations to Sales, Purchase, StockAdjustment via (company, <id>)
      sales = models.ForeignObject(
            "Sales",
            on_delete=models.CASCADE,
            null=True,
            related_name="inventory",
            from_fields=("company", "bill_id"),
            to_fields=("company", "inum"),
      )
      purchase = models.ForeignObject(
            "Purchase",
            null=True,
            on_delete=models.CASCADE,
            from_fields=("company", "pur_bill_id"),
            to_fields=("company", "inum"),
      )
      stock_adjustment = models.ForeignObject(
            "StockAdjustment",
            null=True,
            on_delete=models.CASCADE,
            from_fields=("company", "adj_bill_id"),
            to_fields=("company", "inum"),
      )

class Sales(CompanyModel, PartyVoucher, GstVoucher) :
      discount = decimal_field()
      roundoff = decimal_field()
      type = CharField(max_length=15)
      tds = decimal_field()
      tcs = decimal_field()
      pk = CompositePrimaryKey("company", "inum")
      party = models.ForeignObject(
            "Party",
            on_delete=models.DO_NOTHING,
            null = True,
            from_fields=("company", "party_id"),
            to_fields=("company", "code"),
      )
      class Meta: # type: ignore
        verbose_name_plural = 'Sales'

      class SalesUserManager(models.Manager):
            def for_user(self, user):
                  # Returns only sales related to the user’s company
                  return self.get_queryset().filter(company__user=user)
      user_objects = SalesUserManager()
      objects = models.Manager()

      @transaction.atomic
      def update_and_log(self, field: str, value , notes: str):
          old_value = self.__getattribute__(field)
          self.__setattr__(field,value)
          self.save(update_fields=[field])
          SalesChanges.objects.create(
                  company_id = self.company_id,
                  bill_id = self.inum,
                  field=field,
                  notes=notes,
                  old_value=old_value,
                  new_value=value,
          )

class Discount(CompanyModel): 
      bill_id = models.CharField(max_length=20)
      sub_type = CharField(max_length=20)
      type = CharField(null=True,blank=True,max_length=20)
      amt =  decimal_field()
      moc = CharField(max_length=30,null=True,blank=True)
      class Meta : 
            # unique_together = ("sub_type","bill_id")
            verbose_name_plural = 'Discount'
        
class Purchase(CompanyModel, PartyVoucher, GstVoucher) : #No txval 
      #txval = FloatField(null=True)
      type = CharField(max_length=15,db_default="purchase",null=True)
      ref = CharField(max_length=15,null=True)
      tds = decimal_field()
      tcs = decimal_field()
      pk = CompositePrimaryKey("company", "inum")
      party = models.ForeignObject(
            "Party",
            on_delete=models.CASCADE,
            from_fields=("company", "party_id"),
            to_fields=("company", "code"),
      )
      class Meta :  # type: ignore
            verbose_name_plural = 'Purchase'
      
class StockAdjustment(CompanyModel) : 
      inum = CharField(max_length=20)
      date = DateField()
      godown = CharField(max_length=20,null=True)
      pk = CompositePrimaryKey("company", "inum")


class SalesChanges(CompanyModel) : 
      bill_id = models.CharField(max_length=20,db_index=True)
      field = CharField(max_length=20)
      notes = CharField(max_length=200,null=True,blank=True)
      old_value = CharField(max_length=100,null=True,blank=True)
      new_value = CharField(max_length=100,null=True,blank=True)
      sales = models.ForeignObject(
            "Sales",
            on_delete=models.DO_NOTHING,
            null=True,
            from_fields=("company", "bill_id"),
            to_fields=("company", "inum"),
      )