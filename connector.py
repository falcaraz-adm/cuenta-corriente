"""
Conector a Supabase para Cuenta Corriente (standalone).
"""
import pandas as pd
import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def _get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["service_role_key"]
    return create_client(url, key)


def _sb() -> Client:
    return _get_client()


def _fmt(val):
    if val is None:
        return None
    try:
        return pd.to_datetime(val).strftime("%Y-%m-%d")
    except Exception:
        return None


# ── Proveedores ───────────────────────────────────────────────────────────────

def get_proveedores_cc() -> pd.DataFrame:
    try:
        res = _sb().table("proveedores_cc").select("*").order("fecha_vencimiento", desc=False).execute()
        if not res.data:
            return pd.DataFrame()
        df = pd.DataFrame(res.data)
        for col in ["fecha_recibida", "fecha_vencimiento", "fecha_pago", "fecha_carga"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        return df
    except Exception as e:
        st.error(f"❌ Error al cargar proveedores: {e}")
        return pd.DataFrame()


def add_proveedor_cc(data: dict) -> bool:
    data = data.copy()
    for f in ["fecha_recibida", "fecha_vencimiento", "fecha_pago"]:
        if f in data:
            data[f] = _fmt(data[f])
    data.pop("id", None)
    try:
        _sb().table("proveedores_cc").insert(data).execute()
        return True
    except Exception as e:
        print(f"Error insert proveedor_cc: {e}")
        return False


def update_proveedor_cc(entry_id: int, data: dict) -> bool:
    data = data.copy()
    for f in ["fecha_recibida", "fecha_vencimiento", "fecha_pago"]:
        if f in data:
            data[f] = _fmt(data[f])
    data.pop("id", None)
    try:
        _sb().table("proveedores_cc").update(data).eq("id", entry_id).execute()
        return True
    except Exception as e:
        print(f"Error update proveedor_cc: {e}")
        return False


def delete_proveedor_cc(entry_id: int) -> bool:
    try:
        _sb().table("proveedores_cc").delete().eq("id", entry_id).execute()
        return True
    except Exception as e:
        print(f"Error delete proveedor_cc: {e}")
        return False


# ── Clientes ──────────────────────────────────────────────────────────────────

def get_clientes_cc() -> pd.DataFrame:
    try:
        res = _sb().table("clientes_cc").select("*").order("fecha_vencimiento", desc=False).execute()
        if not res.data:
            return pd.DataFrame()
        df = pd.DataFrame(res.data)
        for col in ["fecha_emision", "fecha_vencimiento", "fecha_cobro", "fecha_carga"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        return df
    except Exception as e:
        st.error(f"❌ Error al cargar clientes: {e}")
        return pd.DataFrame()


def add_cliente_cc(data: dict) -> bool:
    data = data.copy()
    for f in ["fecha_emision", "fecha_vencimiento", "fecha_cobro"]:
        if f in data:
            data[f] = _fmt(data[f])
    data.pop("id", None)
    try:
        _sb().table("clientes_cc").insert(data).execute()
        return True
    except Exception as e:
        print(f"Error insert cliente_cc: {e}")
        return False


def update_cliente_cc(entry_id: int, data: dict) -> bool:
    data = data.copy()
    for f in ["fecha_emision", "fecha_vencimiento", "fecha_cobro"]:
        if f in data:
            data[f] = _fmt(data[f])
    data.pop("id", None)
    try:
        _sb().table("clientes_cc").update(data).eq("id", entry_id).execute()
        return True
    except Exception as e:
        print(f"Error update cliente_cc: {e}")
        return False


def delete_cliente_cc(entry_id: int) -> bool:
    try:
        _sb().table("clientes_cc").delete().eq("id", entry_id).execute()
        return True
    except Exception as e:
        print(f"Error delete cliente_cc: {e}")
        return False


# ── Conciliación ──────────────────────────────────────────────────────────────

def marcar_conciliado_proveedor(entry_id: int, ref: str) -> bool:
    try:
        _sb().table("proveedores_cc").update({
            "conciliado": True, "conciliacion_ref": ref
        }).eq("id", entry_id).execute()
        return True
    except Exception as e:
        print(f"Error marcar_conciliado_proveedor: {e}")
        return False


def marcar_conciliado_cliente(entry_id: int, ref: str) -> bool:
    try:
        _sb().table("clientes_cc").update({
            "conciliado": True, "conciliacion_ref": ref
        }).eq("id", entry_id).execute()
        return True
    except Exception as e:
        print(f"Error marcar_conciliado_cliente: {e}")
        return False


def desmarcar_conciliado_proveedor(entry_id: int) -> bool:
    try:
        _sb().table("proveedores_cc").update({
            "conciliado": False, "conciliacion_ref": None
        }).eq("id", entry_id).execute()
        return True
    except Exception as e:
        return False


def desmarcar_conciliado_cliente(entry_id: int) -> bool:
    try:
        _sb().table("clientes_cc").update({
            "conciliado": False, "conciliacion_ref": None
        }).eq("id", entry_id).execute()
        return True
    except Exception as e:
        return False
