from app.company_models import UserSession
import app.models as models
from app.einvoice import create_einv_json

user = models.User.objects.get(username="devaki")
qs = models.Sales.user_objects.for_user(user).filter(type = "salesreturn", inum = "AA026562")
with open("einv.json","w+") as f : 
    f.write(create_einv_json(qs,seller_json=UserSession.objects.get(user="devaki",key="einvoice").config["seller_json"]))

