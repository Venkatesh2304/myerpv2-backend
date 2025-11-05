import datetime
from io import BytesIO
from app.company_models import UserSession
import app.models as models
from app.einvoice import create_einv_json
from custom.classes import IkeaDownloader

user = models.User.objects.get(username="devaki")
inum = "CA01539"
qs = models.Sales.user_objects.for_user(user).filter(inum = inum)
ikea_einv_json:BytesIO = IkeaDownloader("devaki_urban").einvoice_json(fromd = datetime.date(2025,10,30), tod = datetime.date(2025,10,30),bills=[inum])
with open("ikea_einv.json","wb+") as f :
    f.write(ikea_einv_json.getvalue())
    
with open("einv.json","w+") as f : 
    f.write(create_einv_json(qs,seller_json=UserSession.objects.get(user="devaki",key="einvoice").config["seller_json"]))

