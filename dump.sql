--
-- PostgreSQL database dump
--

-- Dumped from database version 15.10 (Ubuntu 15.10-1.pgdg22.04+1)
-- Dumped by pg_dump version 17.2 (Ubuntu 17.2-1.pgdg22.04+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: app_user; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.app_user VALUES ('pbkdf2_sha256$1000000$8ndjnULaX0SESITPmvTFeu$Wew1+HSFsxc1fRAhGjgBCQiampkHYac6ft7IYUq5gIc=', '2025-11-07 09:32:01.994755+05:30', false, '', '', '', false, true, '2025-11-04 20:54:31.268047+05:30', 'devaki');


--
-- Data for Name: app_company; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.app_company VALUES ('devaki_hul', 'devaki', '["sales", "salesreturn", "claimservice", "damage"]');
INSERT INTO public.app_company VALUES ('devaki_rural', 'devaki', '["sales", "salesreturn", "claimservice", "damage"]');
INSERT INTO public.app_company VALUES ('devaki_urban', 'devaki', '["sales", "salesreturn", "claimservice", "damage"]');


--
-- Data for Name: app_usersession; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.app_usersession VALUES ('devaki', 'gst', 'DEVAKI9999', 'Ven@2026', '[{"name": "AuthToken", "path": "/", "value": "3278e79e7bcb44a889eae6c3e2dda789", "domain": ".gst.gov.in"}, {"name": "EntityRefId", "path": "/", "value": "T330001374181", "domain": ".gst.gov.in"}, {"name": "UserName", "path": "/", "value": "devaki9999", "domain": ".gst.gov.in"}, {"name": "TS01b8883c", "path": "/", "value": "0140752c737744b5657dee90cc5ca8b90ee6156d62ac70907aee41d706d9da4b5ce4befa067b9db10a88a1b20ccbed6bc4966d1f2e", "domain": ".services.gst.gov.in"}]', '{"gstin": "33AAPFD1365C1ZR"}');
INSERT INTO public.app_usersession VALUES ('devaki_rural', 'ikea', 'IIT', 'Abc@123456', '[]', '{"home": "https://leveredge57.hulcd.com", "dbName": "41B862", "bill_prefix": "CB", "auto_delivery_process": true}');
INSERT INTO public.app_usersession VALUES ('devaki_hul', 'ikea', 'IIT', 'Ven@1234', '[{"name": "JSESSIONID", "path": "/rsunify", "value": "7913346DD9908EF7CD8B69C1204CD218", "domain": "leveredge18.hulcd.com"}]', '{"home": "https://leveredge18.hulcd.com", "dbName": "41A392", "bill_prefix": "A", "auto_delivery_process": true}');
INSERT INTO public.app_usersession VALUES ('devaki_urban', 'ikea', 'IIT', 'Abc@123456', '[{"name": "JSESSIONID", "path": "/rsunify", "value": "1A3DCCFB5873912FF7A4ADFAF51BDDA0", "domain": "leveredge11.hulcd.com"}]', '{"home": "https://leveredge11.hulcd.com", "dbName": "41B864", "bill_prefix": "CA", "auto_delivery_process": true}');
INSERT INTO public.app_usersession VALUES ('devaki', 'einvoice', 'DEVAKI9999', 'Ven@2345', '[{"name": "TS014913e0", "path": "/", "value": "01eb995384d88d4a68332d5d0e4adfdbdc8596fa936623fe915434fa599e2d81b2b2c88974fad868e0bb22d04d0967162ca088cf9811e2779f98743ef9c3e090bccd07aee00c9b10704c4e6cde65eee5eb1cb2cebaee1be609f3f3f59a0413df6c9e7adc193b5d26dea70734f1ecd477446c9369cb", "domain": ".einvoice1.gst.gov.in"}, {"name": ".AspNetCore.Antiforgery.CnNnqVpGKBs", "path": "/", "value": "CfDJ8JpTKZ0lxSRDoYf_Eu9dZIJxiv0scDcmtb17uXreSsDg2oJZL4t2QlsV5BUF0Z6EKqninKknIPx6RbmPXgOg9zn2h8Z6xr7WAXWHnoRLzzqRgxgjmNIw83cC517nb67jdj8MG0rylBpKxEWJOtBR_ms", "domain": "einvoice1.gst.gov.in"}, {"name": ".AspNetCore.Mvc.CookieTempDataProvider", "path": "/", "value": "CfDJ8JpTKZ0lxSRDoYf_Eu9dZIJJxVUQwMJcl8j6JRQ9r8KCkiHHPS5CoUSz8iG1Spyb7JnVO78OYy8HESxbuUb0zJTvthsipydMH9iyMVQXCiMM42fK--7MDuM8l5ifM_hkBl9FmPpfnNoh0tETy5eQuYs_QUywqcwJv-pqWN7GbVPSAucUoRfH2OkeBaqatri2HB6nOhqX-4ejTUsi__FpOC1A987vfhc5nEvd4jb1_UqWgJowHReIMPxmZnmu8FyAUKLXgfs5m8cnbjJBHb4Vgw1kUhw6sJMELnUf1sVFn9XfM6yE1Z_CgjYCqr-QhqLcwxMZ1AL8ScGQRXYBILNaTP6gyQmGs9_fjMbCeGELXN-IMA002-69QVrt3WfSZInwgP44pXPC7h8ksQNoNs8tqwQ64jXKMT8vm6sufkdHD1gbuGVj1XA3bAENgdVH_cFwB3ODru913-be3-O9CutWhNBZMdU8T9gkDg34pG05H9_vvz-Cp7NiHcjdDQPJSsMu6k13M1b0hDcuZAaSOh09-m4J5C20wtpMibQhwU3vAIZTZ2sevgj8rJJ8kRzygTn5BI5vVXszNlbqylDLR5TGUvv1up06Mz3MaVCnoQ7yjTgeQFAZqB3Lfzzd1tsZ6OUSsDL9mhmSFZQTHoZrV1ksnTAljYD32kmu4N6FmXieQwb8JoIfQWsSanFsFaqUW5Mn0wGhmJt167CfPnd7CVORPGJTDZ4F9l5tOCZbyt4XCNPAtxWYePWFi7vDG23DIg32FGCD10v1g8pjiUKt1ScGiDze9RfKJnmELQdouAsb0U_rjpjmhKIe11zfOti673nV2zP2riPXRz6AISZZajOM9UnIhmi6ME-Ikx2kkzHCd385VnSvMxfeJ65eNQWaf3dH4J-Y1A_pZGPKdTFiZfPWjyM25gBmWqHSY8W_N5BJPy6tVUPo2KNu6CEkxNvliF9vWYjH-H1aGvQYn596bHdaoxMNhxP2xe9xESpe3IDIOzdHW9WC65kMR4RO1KZ7qIaqrw59gqAy6iQ5fIQtO0tBvdAjaCLFMGxz1Ubk6XAh6AOTPWSUIoRD8VUxWbTivasKxGoYaNmtEe-BkGbP5yZMVILxHnW4j8SeD7qbKefJo0gRzxMM_S3EItEaSX8JOW62gObadV5KL_7Uxc1MEmMc0rhtSHUgT_KQT8-ITuYZfIfcAZ7K7oWKRsVx2pAl6-_MeCtuDfy7Tlg7__4jfX7fTA_VY3qvhh7q6PGLDOS63nlWBS-InQAwz3GYCwbebRVZZyod5BuR1y7jKoRszGJBvWOkO4BRV3xm6jhAoeANg-dmtZRrrJG7IZzwS5s_nMw0s1SV_JEW2UykhlAq-keAJIqD4dzAtsNHQ_6bwLoWR8Mmxv2U8phDcnxCkBKL81azAubvhgA7Mkv9-WpHN5YEY7uy2ZWkN071nTyGgJ-2v2zWU1elPUWt6AQ-pNskM5WLKe53WLFcyHbnmjJSPlXoBOcPOU0y0qsmNEnPUMJIsK8uLCUm-7ebpf_4jNQLB2mBaF6l5ioNWRmICUHwyYMs8buX-5rhrEG1asZJYX_dxVSOv15_QmAePHzttZOgn0I5e-wBliXE5YK5X5YrdTGZs361f7AT5yTbLIbEse_ugOwTcp1Wi3kKqLFpqDbjq6S9YX7U2SUTQAqBYUEv2OevMbT9SZ-vjjIixp5gu5xO097BMvj7fTZmm2_xjwmllUJFnVEvhA4rZku1uB8BxwBDcj4qybs2EkzFzjSlNUXxxGgT8fFUhSfxclCKThDUKg_c9O2GYG623MwKKFWCIWOQUzX-3OmVo9AxJu-guYd5HMnfprfBkkrGPULHVCGB1RFqnsu_ZHc9ABLCqubvxMqWcq9nalKjqOrTiiWJLJbZQpEnz1n6yBbcc_JaT0HBkrZlXf0ct8hqe3Htp7x1siRkNBRTN2GUNm4_v0Fm8zfYxif0RuU-7WNymDzD9ytaTqeuSg7DJPC0VL3f62w3-wH31vG_oRMKhefAq5q0tj8F9Fdf52iEmhPpDgoMJiPSe7nDHJpKqy0flb7VeFxArBOABNDhBjOaL4VYxFKN16pP5v5keBX54NfjvKGd8kiPrgHNbwRdY6o052UQJcng6U1j2ihgKsUHlmehgZRuYPOhMrKZAfHxJeLh068HxsiHB1FpiD4d9irSRHrksaiNHby-I4Siwd1MMsPG7S21aJwqb2Wyg_x23TS2aY-dXo0Q7P6f-g1RXwVjALgyjTAD0V6T5Yo_nCndjzag-j3qkPaVnL-PpwkEwItObGDbx2bCM58dS-HHZHZ86D5EgfpYJHEEXaByWINljv637se0cjW_jqBBH0ScGtnw8B8sQrKEvIbzgdpXGibZSgkVUJN4vpmBfZSvRjBgdnlndB2NvaawF1yggPnnCAjzO6D2wfH0mlclk_iPCJ3psY7jJmMaFRSg5Ef6VQoiW59HpWKRK9VphQdvq9uWB1aqR1Mivqf3_wXZA7kn3uD_166BD98_B-xIYOkS_7yd9Z7ABxYBJkkaDWRpwCi1mIKLWwKbGvK_eFp0Jscu3LLyQZzcUMRZG2gf4_EhUDjGYFwQZudkvZVQMvGuZD3bKKLEZa_ntnV8ilFNZMBVpk6HLnF5bxZbU9y2v9_drLjCQYIbuv_t_qx66Vf6JnC9PGV607eezz_A5E1TwC_MviMMEqNXo0dbRHi54fKm9fOLUX-S_zT6Btn5tnYKwhyE695XVPyMV5C3OEcoqomhB_E6f6h5E4iV6gguN1q4dp_zNvEAVlSkoJq1HoavYeyGhiNaibPgP9GRfZQ-VbWaE3-N34QhUcjI5SiwP0wvX6eO7oldDf3vtyYLoIV4-wbQmiCtj5ecA4YszDvR9PF84_bmTawO9UXArbVYJtOakhLe0V_uyDDNz1asce_vRSB-bOiBi04VJQ4aI8xh96n8tGWjINKbOtZ_GtWw7vVIzjNk-EDeyPwcxAbMysj_uikcwssoANp-EAhjusqRD-lbT_FT16S7SUHh460HzXM", "domain": "einvoice1.gst.gov.in"}, {"name": "gsteinvoice", "path": "/", "value": "CfDJ8JpTKZ0lxSRDoYf_Eu9dZIIQvM2PUm3ScawWUAmaAqHtr001-Y_eo5WKhumispb6Af6Q1jA9ddqhhn957Vt9DWSm1gO2tWGqNyTFbMG03RyuaiCr5AXyoVXlKmXvefucCGvcx_nzRxBuaIWpvn19WdHjyw8x8OUlU5_zp-ZgSHBdDmMTM4rUP-RicVfxRwbbA1FAmVHT9gTiquzfB9FfqQjTmjLkvSu3rV9Sb7Gqe0keaZTciArdSMr4Wla5E9Gytka1Ev6X9WDc6yTLmysehVqFF7KaOhdLXcu0aDRwlcx_TE-LhNFm7bZSNdqVvUxi9LgQCneSf6MuJBPAUqN0K0lrqBS2E8oz_bU_ShJwWkgMbEEHvpXhwKkNbYAADa6fpPlouQ7kw00uFKnYtsX7I2qL8TTf7CqsfyLBs4ciXMRFP71Na-PEKwUERTEtgrAb6s36tP-m0zjM3UEGF83rzRMJT0vwfKw2mrEa2qekycfy18nNTMgjK2nyxJOaWXUzEi_tLKyJ6YJ83KSn258tfol_KMpYRcaQkjvFZ__LI5Ep2TIt7yZwEbDm-prAuj3pqPI3rKOGWs3wzamVN_QfdDniTHd-gkeK9CQZzDBfLsVxUJJBBBNMJhoQ01qiyLH8JW6YAl1_C4l9YjQ4BmhN75hBdVmJ_ourJncqyBJnYY-nRmvA1d6R8Xq9L3iSAQsLYFV7Uw3xF6gsGUsqyJJj1_773UR3ug_wbI53b_510F12lWgzZv62rU4GO1fYviUkfVydKIKcHvoL-5xPvQSIesOvLVkuTBcu7VQR5l6l2QZGManwSDK8u9__C2-11paJjZaMMctUiaUTMpOoLhZ5GzbNnt1bIyN8K_H_Z5PdlnlrShcowZcaTMEcRCy7g7fYrJeV-m5qw_C8giHuzAemjQnY4OcEZWH7jbfIog5f7o4PIEESqsWdxl85vZx0T6xsUvG0EKRwp6xLZmniGy8oo2oRwgx1Z5rfXwYZj-l4dQCpmT3StrRqJIr0OQmNBvMmRgnLygYdfbiqlaP-elWVii8ocI1eFp0iP3d9xw_LFplBprb_YpdsJE7pruAkTojWKA", "domain": "einvoice1.gst.gov.in"}, {"name": "ewb_ld_cookie", "path": "/", "value": "292419338.20480.0000", "domain": "ewaybillgst.gov.in"}]', '{"form": {"CaptchaCode": "", "UserLogin.Password": "", "UserLogin.UserName": "", "UserLogin.PasswordMD5": "", "__RequestVerificationToken": "CfDJ8JpTKZ0lxSRDoYf_Eu9dZIL_eAW2dvxw0ODKQYs3qor1u4YVTIcCJMdagxKZnBLAE8Wt9IPH_VfLNWZIikO0p9xqe5IjHvS-OPaYH6ueJ3uK4SlXvAYWvzoNmsQWMd2iR4xmAuEZxskifH_Meodfihg", "UserLogin.HiddenPasswordSha": ""}, "seller_json": {"SellerDtls": {"Loc": "TRICHY", "Pin": 620010, "Stcd": "33", "Addr1": "F/4 , INDUSTRISAL ESTATE , ARIYAMANGALAM", "Gstin": "33AAPFD1365C1ZR", "LglNm": "DEVAKI ENTERPRISES"}}}');


--
-- PostgreSQL database dump complete
--

