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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: app_user; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.app_user (
    password character varying(128) NOT NULL,
    last_login timestamp with time zone,
    is_superuser boolean NOT NULL,
    first_name character varying(150) NOT NULL,
    last_name character varying(150) NOT NULL,
    email character varying(254) NOT NULL,
    is_staff boolean NOT NULL,
    is_active boolean NOT NULL,
    date_joined timestamp with time zone NOT NULL,
    username character varying(150) NOT NULL
);


ALTER TABLE public.app_user OWNER TO postgres;

--
-- Data for Name: app_user; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.app_user (password, last_login, is_superuser, first_name, last_name, email, is_staff, is_active, date_joined, username) FROM stdin;
pbkdf2_sha256$1000000$8ndjnULaX0SESITPmvTFeu$Wew1+HSFsxc1fRAhGjgBCQiampkHYac6ft7IYUq5gIc=	2025-11-07 09:32:01.994755+05:30	f				f	t	2025-11-04 20:54:31.268047+05:30	devaki
\.


--
-- Name: app_user app_user_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.app_user
    ADD CONSTRAINT app_user_pkey PRIMARY KEY (username);


--
-- Name: app_user_username_9d6296ff_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX app_user_username_9d6296ff_like ON public.app_user USING btree (username varchar_pattern_ops);


--
-- PostgreSQL database dump complete
--

