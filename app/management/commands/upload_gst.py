import os
import json
import time
from django.core.management.base import BaseCommand, CommandError
from app.company_models import User
from custom.classes import Gst

class Command(BaseCommand):
    help = "Upload GST JSON for a user and GST period (MMYYYY). Usage: manage.py upload_gst <username> <gst_period>"

    def add_arguments(self, parser):
        parser.add_argument("username", type=str, help="Django username")
        parser.add_argument("gst_period", type=str, help="GST period in MMYYYY format")

    def handle(self, *args, **options):
        username = options["username"]
        period = options["gst_period"]

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"User '{username}' not found")

        json_path = f"static/{username}/{period}.json"
        if not os.path.exists(json_path):
            raise CommandError(f"GST JSON not found at {json_path}. Generate it first.")

        gst_client = Gst(username)

        if not gst_client.is_logged_in():
            raise CommandError("GST session not logged in. Complete captcha login via existing API flow before uploading.")

        gst_info = gst_client.getuser()
        self.stdout.write(f"GST Name: {gst_info}")
        input("Press Enter to continue with GST upload...")
        gst_client.upload(period, json_path)
        
        # Replicate Gst.upload without the initial input prompt
        files = {
            'upfile': (
                "gst.json",
                open(json_path, "rb"),
                'application/json',
                {'Content-Disposition': 'form-data'}
            )
        }
        try:
            referer_hdr = {"Referer": "https://return.gst.gov.in/returns/auth/gstr/offlineupload"}
            init_resp = gst_client.post(
                "https://return.gst.gov.in/returndocs/offline/upload",
                headers=referer_hdr | {"sz": "304230"},
                data={"ty": "ROUZ", "rtn_typ": "GSTR1", "ret_period": period},
                files=files
            ).json()
            ref_id = init_resp['data']['reference_id']

            gst_client.post(
                "https://return.gst.gov.in/returns/auth/api/gstr1/upload",
                headers=referer_hdr,
                json={"status": "1", "data": {"reference_id": ref_id}, "fp": period}
            )

            status = None
            for _ in range(90):
                time.sleep(1)
                summary = gst_client.get(
                    f"https://return.gst.gov.in/returns/auth/api/offline/upload/summary?rtn_prd={period}&rtn_typ=GSTR1",
                    headers=referer_hdr
                ).json()["data"]["upload"]
                for s in summary:
                    if s.get("ref_id") == ref_id:
                        status = s
                        break
                if status:
                    break

            if not status:
                raise CommandError("Timed out waiting for upload status.")

            self.stdout.write(json.dumps(status, indent=2))

            if status.get("status") == "PE":
                # Generate error file
                gst_client.get(
                    f"https://return.gst.gov.in/returns/auth/api/offline/upload/error/generate?ref_id={ref_id}&rtn_prd={period}&rtn_typ=GSTR1",
                    headers=referer_hdr
                )
                self.stdout.write("Errors detected. Error file requested from portal.")
        finally:
            try:
                files['upfile'][1].close()
            except Exception:
                pass