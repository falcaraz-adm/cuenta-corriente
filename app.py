"""
Cuenta Corriente — App Standalone
Seguimiento de facturas de proveedores y clientes (Guatemala).
"""
import streamlit as st
import pandas as pd
import datetime
import io

st.set_page_config(
    page_title="Cuenta Corriente",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from connector import (
    get_proveedores_cc, add_proveedor_cc, update_proveedor_cc, delete_proveedor_cc,
    get_clientes_cc,    add_cliente_cc,    update_cliente_cc,    delete_cliente_cc,
)

# ── Constantes ────────────────────────────────────────────────────────────────

PAISES = [
    "GUATEMALA", "ARGENTINA", "URUGUAY", "CHILE",
    "PARAGUAY", "BOLIVIA", "AXT", "CANOA", "NAVEGANTES",
]

C_SUCCESS = "#00D68F"
C_DANGER  = "#FF3D71"
C_WARNING = "#FFAA00"
C_INFO    = "#0095FF"
C_BORDER  = "#2D3348"
C_MUTED   = "#6B7280"

COUNTRY_THEMES = {
    "TODOS":      {"primary": "#6C63FF", "secondary": "#4B4899", "flag": "🌎", "name": "Todos"},
    "GUATEMALA":  {"primary": "#4B9CD3", "secondary": "#0F4C81", "flag": "🇬🇹", "name": "Guatemala"},
    "ARGENTINA":  {"primary": "#74ACDF", "secondary": "#003087", "flag": "🇦🇷", "name": "Argentina"},
    "URUGUAY":    {"primary": "#5BA4CF", "secondary": "#002868", "flag": "🇺🇾", "name": "Uruguay"},
    "CHILE":      {"primary": "#D52B1E", "secondary": "#003087", "flag": "🇨🇱", "name": "Chile"},
    "PARAGUAY":   {"primary": "#0038A8", "secondary": "#D52B1E", "flag": "🇵🇾", "name": "Paraguay"},
    "BOLIVIA":    {"primary": "#007A3D", "secondary": "#D52B1E", "flag": "🇧🇴", "name": "Bolivia"},
    "AXT":        {"primary": "#6C63FF", "secondary": "#4B4899", "flag": "🏢", "name": "AXT"},
    "CANOA":      {"primary": "#00D68F", "secondary": "#007A4D", "flag": "🏢", "name": "Canoa"},
    "NAVEGANTES": {"primary": "#0095FF", "secondary": "#0060B0", "flag": "🏢", "name": "Navegantes"},
}

# ── CSS global ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
header {visibility: hidden;}
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: #0E1117; }
::-webkit-scrollbar-thumb { background: #2D3348; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #6C63FF; }
h1, h2, h3 { font-family: 'Outfit','Inter',sans-serif !important; font-weight: 700 !important; }
div[data-testid="metric-container"] {
    background: linear-gradient(135deg,#1A1F2E 0%,#252B3B 100%);
    border: 1px solid #2D3348; border-radius: 12px;
    padding: .8rem 1.2rem; box-shadow: 0 4px 10px rgba(0,0,0,.15);
}
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_date(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "—"
    try:
        return pd.Timestamp(val).strftime("%d/%m/%Y")
    except Exception:
        return "—"


def _safe(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val)


def _estado_visual_prov(row, hoy):
    estado = row.get("estado", "PENDIENTE")
    if estado == "PAGADA":
        return "PAGADA"
    fv = row.get("fecha_vencimiento")
    if pd.notna(fv) and pd.Timestamp(fv).date() < hoy:
        return "VENCIDA"
    if estado == "SIN_FACTURA":
        return "SIN_FACTURA"
    return "PENDIENTE"


def _estado_visual_cli(row, hoy):
    if row.get("estado") == "COBRADA":
        return "COBRADA"
    fv = row.get("fecha_vencimiento")
    if pd.notna(fv) and pd.Timestamp(fv).date() < hoy:
        return "VENCIDA"
    return "PENDIENTE"


_BADGE_CFG = {
    "SIN_FACTURA": (C_INFO,    "📄", "SIN FACTURA"),
    "PENDIENTE":   (C_WARNING, "⏳", "PENDIENTE"),
    "VENCIDA":     (C_DANGER,  "🔴", "VENCIDA"),
    "PAGADA":      (C_SUCCESS, "✅", "PAGADA"),
    "COBRADA":     (C_SUCCESS, "✅", "COBRADA"),
}


def _badge(estado):
    color, icon, label = _BADGE_CFG.get(estado, (C_MUTED, "❓", estado))
    return (
        "<span style='display:inline-block;padding:3px 10px;border-radius:20px;"
        "background:" + color + "22;color:" + color + ";border:1px solid " + color + "55;"
        "font-size:.78rem;font-weight:700;white-space:nowrap;'>" + icon + " " + label + "</span>"
    )


def _dias_label(fv, ev, hoy):
    if ev in ("PAGADA", "COBRADA") or not pd.notna(fv):
        return ""
    days = (pd.Timestamp(fv).date() - hoy).days
    if days < 0:
        return "<span style='color:" + C_DANGER + ";font-size:.73rem;'>(hace " + str(abs(days)) + "d)</span>"
    elif days == 0:
        return "<span style='color:" + C_WARNING + ";font-size:.73rem;'>(¡Hoy!)</span>"
    elif days <= 7:
        return "<span style='color:" + C_WARNING + ";font-size:.73rem;'>(en " + str(days) + "d)</span>"
    return "<span style='color:#A0A4B8;font-size:.73rem;'>(en " + str(days) + "d)</span>"


def _border_color(ev):
    return {
        "SIN_FACTURA": C_INFO,
        "PENDIENTE":   C_WARNING,
        "VENCIDA":     C_DANGER,
        "PAGADA":      C_SUCCESS,
        "COBRADA":     C_SUCCESS,
    }.get(ev, C_BORDER)


def _kpi_card(col, titulo, valor, subtitulo, color):
    col.markdown(
        "<div style='background:linear-gradient(135deg," + color + "18 0%," + color + "08 100%);"
        "border:1px solid " + color + "44;border-radius:12px;padding:1rem;text-align:center;'>"
        "<div style='font-size:.75rem;color:#A0A4B8;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;'>" + titulo + "</div>"
        "<div style='font-size:1.4rem;font-weight:800;color:" + color + ";margin:2px 0;'>" + valor + "</div>"
        "<div style='font-size:.72rem;color:#A0A4B8;'>" + subtitulo + "</div>"
        "</div>",
        unsafe_allow_html=True
    )


def _alert_banner(msg, color):
    st.markdown(
        "<div style='background:" + color + "11;border:1px solid " + color + "66;"
        "border-radius:8px;padding:.6rem 1rem;margin:.4rem 0;'>" + msg + "</div>",
        unsafe_allow_html=True
    )


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages[:3]:
            text += page.extract_text() or ""
        return text.strip()[:2000]
    except Exception:
        return ""


def _ocr_factura_ia(file_bytes: bytes, filename: str) -> dict:
    try:
        api_key = st.secrets.get("anthropic", {}).get("api_key", "")
        if not api_key:
            return {"error": "Falta [anthropic] api_key en Secrets. Agregá: [anthropic]\napi_key = 'sk-ant-...'"}
        import anthropic, base64, json, re
        client_ai = anthropic.Anthropic(api_key=api_key)
        ext = filename.lower().rsplit(".", 1)[-1]
        prompt = (
            "Analizá esta factura y extraé los datos en JSON con estas claves exactas:\n"
            '{"nombre": "empresa o persona que emite", "numero_factura": "número", '
            '"monto": 0.00, "moneda": "GTQ", '
            '"fecha_emision": "YYYY-MM-DD", "fecha_vencimiento": "YYYY-MM-DD", '
            '"descripcion": "descripción del servicio"}\n'
            "Si un dato no aparece usá null. Respondé SOLO con el JSON."
        )
        if ext == "pdf":
            texto = _extract_pdf_text(file_bytes)
            if texto:
                resp = client_ai.messages.create(
                    model="claude-haiku-4-5-20251001", max_tokens=600,
                    messages=[{"role": "user", "content": f"{prompt}\n\nTexto:\n{texto}"}]
                )
            else:
                b64 = base64.standard_b64encode(file_bytes).decode()
                resp = client_ai.messages.create(
                    model="claude-haiku-4-5-20251001", max_tokens=600,
                    messages=[{"role": "user", "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}},
                        {"type": "text", "text": prompt}
                    ]}]
                )
        else:
            mt = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
            b64 = base64.standard_b64encode(file_bytes).decode()
            resp = client_ai.messages.create(
                model="claude-haiku-4-5-20251001", max_tokens=600,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}},
                    {"type": "text", "text": prompt}
                ]}]
            )
        raw = resp.content[0].text.strip()
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        return json.loads(m.group()) if m else {"error": f"Respuesta inesperada: {raw[:120]}"}
    except Exception as e:
        return {"error": str(e)}


# ═════════════════════════════════════════════════════════════════════════════
# PROVEEDORES
# ═════════════════════════════════════════════════════════════════════════════

def _render_proveedores(pais_sel="TODOS", theme_color="#4B9CD3"):
    hoy = datetime.date.today()
    df  = get_proveedores_cc()

    if pais_sel != "TODOS" and not df.empty and "pais" in df.columns:
        df = df[df["pais"] == pais_sel].copy()

    if df.empty:
        df_calc = pd.DataFrame()
    else:
        df["_ev"] = df.apply(lambda r: _estado_visual_prov(r, hoy), axis=1)
        df_calc = df

    def _is_pv7(row):
        fv = row.get("fecha_vencimiento")
        if not pd.notna(fv):
            return False
        return 0 <= (pd.Timestamp(fv).date() - hoy).days <= 7

    df_pend = df_calc[df_calc["_ev"].isin(["PENDIENTE", "SIN_FACTURA", "VENCIDA"])] if not df_calc.empty else pd.DataFrame()
    df_venc = df_calc[df_calc["_ev"] == "VENCIDA"]                                   if not df_calc.empty else pd.DataFrame()
    df_pv7  = df_calc[df_calc["_ev"].isin(["PENDIENTE", "SIN_FACTURA"]) & df_calc.apply(_is_pv7, axis=1)] if not df_calc.empty else pd.DataFrame()

    mes_actual = hoy.month
    if not df_calc.empty:
        mask = (df_calc["_ev"] == "PAGADA") & df_calc["fecha_pago"].notna()
        df_pag_mes = df_calc[mask & df_calc["fecha_pago"].apply(
            lambda x: pd.Timestamp(x).month == mes_actual if pd.notna(x) else False
        )]
    else:
        df_pag_mes = pd.DataFrame()

    total_pend = df_pend["monto_local"].sum()    if not df_pend.empty    else 0
    total_venc = df_venc["monto_local"].sum()    if not df_venc.empty    else 0
    total_pv7  = df_pv7["monto_local"].sum()     if not df_pv7.empty     else 0
    total_pag  = df_pag_mes["monto_local"].sum() if not df_pag_mes.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    _kpi_card(c1, "Total Pendiente",  "Q " + f"{total_pend:,.2f}", str(len(df_pend))    + " facturas", theme_color)
    _kpi_card(c2, "Vencidas",         "Q " + f"{total_venc:,.2f}", str(len(df_venc))    + " facturas", C_DANGER)
    _kpi_card(c3, "Por Vencer (7d)",  "Q " + f"{total_pv7:,.2f}",  str(len(df_pv7))     + " facturas", C_WARNING)
    _kpi_card(c4, "Pagadas este mes", "Q " + f"{total_pag:,.2f}",  str(len(df_pag_mes)) + " pagos",    C_SUCCESS)

    if not df_venc.empty:
        _alert_banner(
            "<b style='color:" + C_DANGER + ";'>🚨 Atención:</b> " + str(len(df_venc)) +
            " factura(s) vencida(s) por <b>Q " + f"{total_venc:,.2f}</b>.",
            C_DANGER
        )

    st.markdown("---")

    tab_seg, tab_nueva, tab_pagar, tab_edit = st.tabs([
        "📋 Seguimiento", "➕ Nueva Entrada", "💳 Registrar Pago", "✏️ Editar / Eliminar",
    ])
    with tab_seg:   _prov_seguimiento(df_calc, hoy)
    with tab_nueva: _prov_nueva_entrada()
    with tab_pagar: _prov_registrar_pago(df_calc, hoy)
    with tab_edit:  _prov_editar(df_calc, hoy)


def _prov_seguimiento(df, hoy):
    if df.empty:
        st.info("No hay entradas registradas. Usá ➕ Nueva Entrada para agregar la primera.")
        return

    col1, col2, col3 = st.columns([1, 1, 1.5])
    with col1:
        f_estado = st.selectbox("Estado", ["Todos", "SIN FACTURA", "PENDIENTE", "VENCIDA", "PAGADA"], key="prov_f_estado")
    with col2:
        provs  = ["Todos"] + sorted(df["proveedor"].dropna().unique().tolist())
        f_prov = st.selectbox("Proveedor", provs, key="prov_f_prov")
    with col3:
        f_busq = st.text_input("Buscar", placeholder="N° factura, observaciones...", key="prov_f_busq")

    df_v       = df.copy()
    estado_map = {"SIN FACTURA": "SIN_FACTURA"}
    if f_estado != "Todos":
        df_v = df_v[df_v["_ev"] == estado_map.get(f_estado, f_estado)]
    if f_prov != "Todos":
        df_v = df_v[df_v["proveedor"] == f_prov]
    if f_busq.strip():
        mask = (
            df_v["numero_factura"].fillna("").str.contains(f_busq, case=False) |
            df_v["proveedor"].fillna("").str.contains(f_busq, case=False) |
            df_v["observaciones"].fillna("").str.contains(f_busq, case=False)
        )
        df_v = df_v[mask]

    orden = {"VENCIDA": 0, "SIN_FACTURA": 1, "PENDIENTE": 2, "PAGADA": 3}
    df_v["_ord"] = df_v["_ev"].map(orden).fillna(4)
    df_v = df_v.sort_values(["_ord", "fecha_vencimiento"]).reset_index(drop=True)

    if df_v.empty:
        st.info("No hay registros que coincidan.")
        return

    st.markdown("<small style='color:#A0A4B8;'>" + str(len(df_v)) + " registro(s)</small>", unsafe_allow_html=True)
    st.markdown("")

    tc = st.session_state.get("tc", "#4B9CD3")
    for _, row in df_v.iterrows():
        ev     = row["_ev"]
        border = _border_color(ev)
        fac    = _safe(row.get("numero_factura")) or "Sin N° factura"
        dias   = _dias_label(row.get("fecha_vencimiento"), ev, hoy)
        monto  = float(row.get("monto_local") or 0)

        pago_info = ""
        if ev == "PAGADA":
            nro = _safe(row.get("numero_transferencia"))
            pago_info = "&nbsp;|&nbsp; 💳 Pagado: <b>" + _fmt_date(row.get("fecha_pago")) + "</b>"
            if nro:
                pago_info += "&nbsp;|&nbsp; 🔢 " + nro

        comp_html = ""
        comp = _safe(row.get("comprobante_nombre"))
        if comp:
            comp_html = "&nbsp;|&nbsp; 📎 " + comp

        obs_html = ""
        obs = _safe(row.get("observaciones"))
        if obs:
            obs_html = "<div style='font-size:.72rem;color:#A0A4B8;margin-top:2px;'>📝 " + obs + "</div>"

        html = (
            "<div style='background:linear-gradient(135deg," + tc + "12 0%,#1A1F2E 100%);"
            "border-left:4px solid " + border + ";"
            "border-radius:8px;padding:.8rem 1.1rem;margin-bottom:.5rem;"
            "box-shadow:0 2px 8px " + tc + "18;'>"
            "<div style='display:flex;justify-content:space-between;align-items:center;gap:1rem;'>"
            "  <div style='flex:4;min-width:0;'>"
            "    <div style='font-weight:700;font-size:.95rem;color:#FAFAFA;'>"
            + _safe(row.get("proveedor")) +
            "      <span style='font-size:.78rem;color:#A0A4B8;font-weight:400;'> · " + fac + "</span>"
            "    </div>"
            "    <div style='font-size:.75rem;color:#A0A4B8;margin-top:4px;line-height:1.6;'>"
            "      📅 Vence: <b>" + _fmt_date(row.get("fecha_vencimiento")) + "</b> " + dias +
            "      &nbsp;|&nbsp; 🗓 Recibida: " + _fmt_date(row.get("fecha_recibida")) +
            pago_info + comp_html +
            "    </div>" + obs_html +
            "  </div>"
            "  <div style='flex-shrink:0;'>" + _badge(ev) + "</div>"
            "  <div style='flex-shrink:0;font-weight:700;color:" + C_DANGER + ";font-size:1rem;white-space:nowrap;'>"
            "    Q " + f"{monto:,.2f}" +
            "  </div>"
            "</div></div>"
        )
        st.markdown(html, unsafe_allow_html=True)


def _prov_nueva_entrada():
    st.markdown("### Registrar nueva factura de proveedor")

    modo = st.radio(
        "¿Cómo querés cargar?",
        ["🤖 Subir factura (IA la procesa)", "📄 Tengo los datos completos", "💰 Solo sé el monto (la factura llega después)"],
        horizontal=True, key="prov_modo_entrada"
    )

    ocr = {}
    if modo.startswith("🤖"):
        archivo = st.file_uploader("Subí la factura (PDF, JPG, PNG)", type=["pdf","jpg","jpeg","png"], key="prov_ocr_file")
        if archivo:
            if st.button("🤖 Procesar con IA", key="prov_ocr_btn", type="primary"):
                with st.spinner("Leyendo factura con IA..."):
                    resultado = _ocr_factura_ia(archivo.read(), archivo.name)
                if "error" in resultado:
                    st.error(f"❌ {resultado['error']}")
                else:
                    st.session_state["prov_ocr"] = resultado
                    st.success("✅ Datos extraídos — revisá y editá si es necesario.")
                    st.rerun()
        ocr = st.session_state.get("prov_ocr", {})
        if ocr:
            with st.expander("📋 Datos extraídos por la IA", expanded=True):
                c1, c2, c3 = st.columns(3)
                c1.metric("Nombre", ocr.get("nombre") or "—")
                c2.metric("Monto", f"{ocr.get('monto') or 0:,.2f} {ocr.get('moneda','GTQ')}")
                c3.metric("N° Factura", ocr.get("numero_factura") or "—")

    if modo.endswith("(la factura llega después)"):
        st.info("**Modo sin factura:** Cuando llegue la factura, editá este registro para completar los datos.")

    tiene_factura = not modo.endswith("(la factura llega después)")

    # Defaults desde OCR
    _def_prov  = _safe(ocr.get("nombre", ""))
    _def_fac   = _safe(ocr.get("numero_factura", ""))
    _def_monto = float(ocr.get("monto") or 0.0)
    _def_obs   = _safe(ocr.get("descripcion", ""))
    try:
        _def_fv = pd.Timestamp(ocr["fecha_vencimiento"]).date() if ocr.get("fecha_vencimiento") else datetime.date.today() + datetime.timedelta(days=30)
    except Exception:
        _def_fv = datetime.date.today() + datetime.timedelta(days=30)

    with st.form("form_nueva_prov", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            proveedor = st.text_input("Proveedor *", value=_def_prov, placeholder="Ej. Impresos del Pacífico SA")
        with c2:
            pais = st.selectbox("País", PAISES, index=PAISES.index("GUATEMALA"))

        c3, c4 = st.columns(2)
        with c3:
            monto_gtq = st.number_input("Monto GTQ *", min_value=0.0, value=_def_monto, step=100.0, format="%.2f")
        with c4:
            monto_usd = st.number_input("Equivalente USD", min_value=0.0, value=0.0, step=10.0, format="%.2f")

        if tiene_factura:
            c5, c6 = st.columns(2)
            with c5:
                num_factura = st.text_input("N° Factura *", value=_def_fac, placeholder="FAC-2026-001")
            with c6:
                fecha_venc = st.date_input("Fecha de Vencimiento *", value=_def_fv)
        else:
            num_factura = ""
            fecha_venc  = st.date_input("Fecha estimada de vencimiento", value=_def_fv)

        obs = st.text_area("Observaciones / Referencia interna", value=_def_obs, placeholder="Ej. Orden de compra #456...", height=70)
        sub = st.form_submit_button("💾 Guardar", type="primary", use_container_width=True)

        if sub:
            if not proveedor.strip():
                st.error("El proveedor es obligatorio.")
            elif monto_gtq <= 0:
                st.error("El monto debe ser mayor a 0.")
            elif tiene_factura and not num_factura.strip():
                st.error("El N° de factura es obligatorio cuando seleccionás 'Tengo la factura'.")
            else:
                data = {
                    "proveedor":         proveedor.strip().upper(),
                    "pais":              pais,
                    "monto_local":       monto_gtq,
                    "moneda":            "GTQ",
                    "monto_usd":         monto_usd,
                    "fecha_vencimiento": fecha_venc,
                    "fecha_recibida":    datetime.date.today(),
                    "estado":            "PENDIENTE" if tiene_factura else "SIN_FACTURA",
                    "tiene_factura":     tiene_factura,
                    "observaciones":     obs.strip() or None,
                    "fecha_carga":       datetime.datetime.now().isoformat(),
                }
                if num_factura.strip():
                    data["numero_factura"] = num_factura.strip().upper()
                ok = add_proveedor_cc(data)
                if ok:
                    st.session_state.pop("prov_ocr", None)
                    st.success("✅ Entrada registrada correctamente.")
                    st.rerun()
                else:
                    st.error("❌ Error al guardar. Verificá que las tablas existan en Supabase (ver setup_cuenta_corriente.sql).")


def _prov_registrar_pago(df, hoy):
    st.markdown("### Registrar pago de factura")

    if df.empty:
        st.info("No hay facturas registradas todavía.")
        return

    df_pend = df[df["_ev"].isin(["PENDIENTE", "SIN_FACTURA", "VENCIDA"])].copy()
    if df_pend.empty:
        st.success("✅ No hay facturas pendientes de pago.")
        return

    options = []
    mapping = {}
    for _, row in df_pend.sort_values("fecha_vencimiento").iterrows():
        fac   = _safe(row.get("numero_factura")) or "S/N"
        ev    = row["_ev"]
        tag   = {"SIN_FACTURA": "[SIN FAC] ", "VENCIDA": "[VENCIDA] "}.get(ev, "")
        monto = float(row.get("monto_local") or 0)
        label = tag + _safe(row.get("proveedor")) + " · " + fac + " · Q " + f"{monto:,.2f}" + " · Vence " + _fmt_date(row.get("fecha_vencimiento"))
        options.append(label)
        mapping[label] = row

    sel  = st.selectbox("Seleccionar factura a pagar", options, key="prov_pago_sel")
    row  = mapping[sel]
    ev   = row["_ev"]
    monto_sel = float(row.get("monto_local") or 0)

    st.markdown(
        "<div style='background:#1A1F2E;border-radius:8px;padding:.7rem 1rem;"
        "border:1px solid " + _border_color(ev) + ";margin:.5rem 0 1rem 0;font-size:.85rem;'>"
        "<b>Proveedor:</b> " + _safe(row.get("proveedor")) +
        " &nbsp;|&nbsp; <b>Monto:</b> Q " + f"{monto_sel:,.2f}" +
        " &nbsp;|&nbsp; <b>Vencimiento:</b> " + _fmt_date(row.get("fecha_vencimiento")) +
        " &nbsp;" + _badge(ev) + "</div>",
        unsafe_allow_html=True
    )

    c1, c2 = st.columns(2)
    with c1:
        fecha_pago   = st.date_input("Fecha de pago *", value=datetime.date.today(), key="prov_fecha_pago")
    with c2:
        nro_transfer = st.text_input("N° Transferencia / Referencia *", placeholder="TRF-2026-00123", key="prov_nro_transfer")

    num_fac_now = ""
    if ev == "SIN_FACTURA":
        st.markdown("---")
        st.markdown("**📄 ¿Ya llegó la factura? Podés asociarla ahora:**")
        num_fac_now = st.text_input("N° de Factura", key="prov_num_fac_pago")

    st.markdown("---")
    st.markdown("**📎 Comprobante bancario PDF — opcional**")
    pdf_file = st.file_uploader("Subir PDF del comprobante", type=["pdf"], key="prov_pdf_upload")

    comprobante_nombre = ""
    if pdf_file is not None:
        comprobante_nombre = pdf_file.name
        texto = _extract_pdf_text(pdf_file.read())
        if texto:
            with st.expander("📄 Texto extraído del PDF"):
                st.text(texto[:1200])
        else:
            st.caption("📎 " + comprobante_nombre + " adjunto.")

    st.markdown("")
    if st.button("✅ Confirmar Pago", type="primary", use_container_width=True, key="prov_confirm_pago"):
        if not nro_transfer.strip():
            st.error("El número de transferencia/referencia es obligatorio.")
        else:
            update_data = {
                "estado":               "PAGADA",
                "fecha_pago":           fecha_pago,
                "numero_transferencia": nro_transfer.strip().upper(),
            }
            if comprobante_nombre:
                update_data["comprobante_nombre"] = comprobante_nombre
            if num_fac_now and num_fac_now.strip():
                update_data["numero_factura"] = num_fac_now.strip().upper()
                update_data["tiene_factura"]  = True
            ok = update_proveedor_cc(int(row["id"]), update_data)
            if ok:
                st.success("✅ Pago registrado. Transferencia: **" + nro_transfer.strip().upper() + "**")
                st.rerun()
            else:
                st.error("❌ Error al registrar el pago.")


def _prov_editar(df, hoy):
    st.markdown("### Editar o eliminar entrada")

    if df.empty:
        st.info("No hay entradas para editar.")
        return

    options = []
    mapping = {}
    for _, row in df.sort_values("fecha_vencimiento", ascending=False).iterrows():
        fac   = _safe(row.get("numero_factura")) or "S/N"
        monto = float(row.get("monto_local") or 0)
        label = "[" + row["_ev"] + "] " + _safe(row.get("proveedor")) + " · " + fac + " · Q " + f"{monto:,.2f}"
        options.append(label)
        mapping[label] = row

    sel = st.selectbox("Seleccionar registro", options, key="prov_edit_sel")
    row = mapping[sel]

    with st.form("form_edit_prov"):
        c1, c2 = st.columns(2)
        with c1:
            edit_prov = st.text_input("Proveedor", value=_safe(row.get("proveedor")))
        with c2:
            pais_val  = _safe(row.get("pais"))
            edit_pais = st.selectbox("País", PAISES, index=PAISES.index(pais_val) if pais_val in PAISES else 0)

        c3, c4 = st.columns(2)
        with c3:
            edit_fac   = st.text_input("N° Factura", value=_safe(row.get("numero_factura")))
        with c4:
            edit_monto = st.number_input("Monto GTQ", min_value=0.0, value=float(row.get("monto_local") or 0), step=100.0, format="%.2f")

        c5, c6 = st.columns(2)
        with c5:
            fv_val  = row.get("fecha_vencimiento")
            fv_def  = fv_val.date() if pd.notna(fv_val) and hasattr(fv_val, "date") else datetime.date.today()
            edit_fv = st.date_input("Vencimiento", value=fv_def)
        with c6:
            est_opts = ["PENDIENTE", "SIN_FACTURA", "PAGADA"]
            est_val  = _safe(row.get("estado"))
            edit_est = st.selectbox("Estado", est_opts, index=est_opts.index(est_val) if est_val in est_opts else 0)

        edit_obs = st.text_area("Observaciones", value=_safe(row.get("observaciones")), height=60)

        btn1, btn2 = st.columns(2)
        with btn1:
            save_ok = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)
        with btn2:
            del_req = st.form_submit_button("🗑️ Eliminar", type="secondary", use_container_width=True)

    if save_ok:
        ok = update_proveedor_cc(int(row["id"]), {
            "proveedor":         edit_prov.strip().upper(),
            "pais":              edit_pais,
            "numero_factura":    edit_fac.strip().upper() or None,
            "monto_local":       edit_monto,
            "fecha_vencimiento": edit_fv,
            "estado":            edit_est,
            "tiene_factura":     edit_est in ("PENDIENTE", "PAGADA") or bool(edit_fac.strip()),
            "observaciones":     edit_obs.strip() or None,
        })
        if ok:
            st.success("✅ Registro actualizado.")
            st.rerun()
        else:
            st.error("❌ Error al guardar cambios.")

    if del_req:
        st.session_state["prov_pending_del"] = int(row["id"])

    if st.session_state.get("prov_pending_del"):
        st.markdown("---")
        st.warning("⚠️ **¿Confirmás la eliminación permanente de:** `" + sel + "`")
        dc1, dc2 = st.columns(2)
        with dc1:
            if st.button("🚨 SÍ, ELIMINAR", type="primary", use_container_width=True, key="prov_del_confirm"):
                ok = delete_proveedor_cc(st.session_state["prov_pending_del"])
                if ok:
                    st.success("✅ Eliminado.")
                    del st.session_state["prov_pending_del"]
                    st.rerun()
                else:
                    st.error("❌ Error al eliminar.")
        with dc2:
            if st.button("Cancelar", use_container_width=True, key="prov_del_cancel"):
                del st.session_state["prov_pending_del"]
                st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# CLIENTES
# ═════════════════════════════════════════════════════════════════════════════

def _render_clientes(pais_sel="TODOS", theme_color="#4B9CD3"):
    hoy = datetime.date.today()
    df  = get_clientes_cc()

    if pais_sel != "TODOS" and not df.empty and "pais" in df.columns:
        df = df[df["pais"] == pais_sel].copy()

    if df.empty:
        df_calc = pd.DataFrame()
    else:
        df["_ev"] = df.apply(lambda r: _estado_visual_cli(r, hoy), axis=1)
        df_calc = df

    def _is_pv7(row):
        fv = row.get("fecha_vencimiento")
        if not pd.notna(fv):
            return False
        return 0 <= (pd.Timestamp(fv).date() - hoy).days <= 7

    df_pend = df_calc[df_calc["_ev"] == "PENDIENTE"] if not df_calc.empty else pd.DataFrame()
    df_venc = df_calc[df_calc["_ev"] == "VENCIDA"]   if not df_calc.empty else pd.DataFrame()
    df_pv7  = df_calc[df_calc["_ev"] == "PENDIENTE"].loc[df_calc[df_calc["_ev"] == "PENDIENTE"].apply(_is_pv7, axis=1)] if not df_calc.empty else pd.DataFrame()

    mes_actual = hoy.month
    if not df_calc.empty:
        mask = (df_calc["_ev"] == "COBRADA") & df_calc["fecha_cobro"].notna()
        df_cob_mes = df_calc[mask & df_calc["fecha_cobro"].apply(
            lambda x: pd.Timestamp(x).month == mes_actual if pd.notna(x) else False
        )]
    else:
        df_cob_mes = pd.DataFrame()

    total_pend = df_pend["monto_local"].sum()    if not df_pend.empty    else 0
    total_venc = df_venc["monto_local"].sum()    if not df_venc.empty    else 0
    total_pv7  = df_pv7["monto_local"].sum()     if not df_pv7.empty     else 0
    total_cob  = df_cob_mes["monto_local"].sum() if not df_cob_mes.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    _kpi_card(c1, "Por Cobrar",        "Q " + f"{total_pend:,.2f}", str(len(df_pend))    + " facturas", theme_color)
    _kpi_card(c2, "Vencidas",          "Q " + f"{total_venc:,.2f}", str(len(df_venc))    + " facturas", C_DANGER)
    _kpi_card(c3, "Por Vencer (7d)",   "Q " + f"{total_pv7:,.2f}",  str(len(df_pv7))     + " facturas", C_WARNING)
    _kpi_card(c4, "Cobradas este mes", "Q " + f"{total_cob:,.2f}",  str(len(df_cob_mes)) + " cobros",   C_SUCCESS)

    if not df_venc.empty:
        _alert_banner(
            "<b style='color:" + C_DANGER + ";'>🚨 Atención:</b> " + str(len(df_venc)) +
            " factura(s) de clientes vencida(s) por <b>Q " + f"{total_venc:,.2f}</b>. Gestioná el cobro.",
            C_DANGER
        )

    st.markdown("---")

    tab_seg, tab_nueva, tab_cobrar, tab_edit = st.tabs([
        "📋 Seguimiento", "➕ Nueva Factura", "💰 Registrar Cobro", "✏️ Editar / Eliminar",
    ])
    with tab_seg:    _cli_seguimiento(df_calc, hoy)
    with tab_nueva:  _cli_nueva_factura()
    with tab_cobrar: _cli_registrar_cobro(df_calc, hoy)
    with tab_edit:   _cli_editar(df_calc, hoy)


def _cli_seguimiento(df, hoy):
    if df.empty:
        st.info("No hay facturas de clientes registradas. Usá ➕ Nueva Factura para agregar la primera.")
        return

    col1, col2, col3 = st.columns([1, 1, 1.5])
    with col1:
        f_estado = st.selectbox("Estado", ["Todos", "PENDIENTE", "VENCIDA", "COBRADA"], key="cli_f_estado")
    with col2:
        clis  = ["Todos"] + sorted(df["cliente"].dropna().unique().tolist())
        f_cli = st.selectbox("Cliente", clis, key="cli_f_cli")
    with col3:
        f_busq = st.text_input("Buscar", placeholder="N° factura, cliente...", key="cli_f_busq")

    df_v = df.copy()
    if f_estado != "Todos":
        df_v = df_v[df_v["_ev"] == f_estado]
    if f_cli != "Todos":
        df_v = df_v[df_v["cliente"] == f_cli]
    if f_busq.strip():
        mask = (
            df_v["numero_factura"].fillna("").str.contains(f_busq, case=False) |
            df_v["cliente"].fillna("").str.contains(f_busq, case=False) |
            df_v["observaciones"].fillna("").str.contains(f_busq, case=False)
        )
        df_v = df_v[mask]

    orden = {"VENCIDA": 0, "PENDIENTE": 1, "COBRADA": 2}
    df_v["_ord"] = df_v["_ev"].map(orden).fillna(3)
    df_v = df_v.sort_values(["_ord", "fecha_vencimiento"]).reset_index(drop=True)

    if df_v.empty:
        st.info("No hay registros que coincidan.")
        return

    st.markdown("<small style='color:#A0A4B8;'>" + str(len(df_v)) + " registro(s)</small>", unsafe_allow_html=True)
    st.markdown("")

    tc = st.session_state.get("tc", "#4B9CD3")
    for _, row in df_v.iterrows():
        ev     = row["_ev"]
        border = _border_color(ev)
        fac    = _safe(row.get("numero_factura")) or "S/N"
        dias   = _dias_label(row.get("fecha_vencimiento"), ev, hoy)
        monto  = float(row.get("monto_local") or 0)

        cobro_info = ""
        if ev == "COBRADA":
            nro = _safe(row.get("numero_referencia"))
            cobro_info = "&nbsp;|&nbsp; 💰 Cobrado: <b>" + _fmt_date(row.get("fecha_cobro")) + "</b>"
            if nro:
                cobro_info += "&nbsp;|&nbsp; 🔢 " + nro

        obs_html = ""
        obs = _safe(row.get("observaciones"))
        if obs:
            obs_html = "<div style='font-size:.72rem;color:#A0A4B8;margin-top:2px;'>📝 " + obs + "</div>"

        html = (
            "<div style='background:linear-gradient(135deg," + tc + "12 0%,#1A1F2E 100%);"
            "border-left:4px solid " + border + ";"
            "border-radius:8px;padding:.8rem 1.1rem;margin-bottom:.5rem;"
            "box-shadow:0 2px 8px " + tc + "18;'>"
            "<div style='display:flex;justify-content:space-between;align-items:center;gap:1rem;'>"
            "  <div style='flex:4;min-width:0;'>"
            "    <div style='font-weight:700;font-size:.95rem;color:#FAFAFA;'>"
            + _safe(row.get("cliente")) +
            "      <span style='font-size:.78rem;color:#A0A4B8;font-weight:400;'> · " + fac + "</span>"
            "    </div>"
            "    <div style='font-size:.75rem;color:#A0A4B8;margin-top:4px;line-height:1.6;'>"
            "      📅 Vence: <b>" + _fmt_date(row.get("fecha_vencimiento")) + "</b> " + dias +
            "      &nbsp;|&nbsp; 📄 Emitida: " + _fmt_date(row.get("fecha_emision")) +
            cobro_info +
            "    </div>" + obs_html +
            "  </div>"
            "  <div style='flex-shrink:0;'>" + _badge(ev) + "</div>"
            "  <div style='flex-shrink:0;font-weight:700;color:" + C_SUCCESS + ";font-size:1rem;white-space:nowrap;'>"
            "    Q " + f"{monto:,.2f}" +
            "  </div>"
            "</div></div>"
        )
        st.markdown(html, unsafe_allow_html=True)


def _cli_nueva_factura():
    st.markdown("### Registrar factura a cobrar")

    modo_cli = st.radio(
        "¿Cómo querés cargar?",
        ["🤖 Subir factura (IA la procesa)", "✏️ Carga manual"],
        horizontal=True, key="cli_modo_entrada"
    )

    ocr_cli = {}
    if modo_cli.startswith("🤖"):
        archivo_cli = st.file_uploader("Subí la factura (PDF, JPG, PNG)", type=["pdf","jpg","jpeg","png"], key="cli_ocr_file")
        if archivo_cli:
            if st.button("🤖 Procesar con IA", key="cli_ocr_btn", type="primary"):
                with st.spinner("Leyendo factura con IA..."):
                    res_cli = _ocr_factura_ia(archivo_cli.read(), archivo_cli.name)
                if "error" in res_cli:
                    st.error(f"❌ {res_cli['error']}")
                else:
                    st.session_state["cli_ocr"] = res_cli
                    st.success("✅ Datos extraídos — revisá y editá si es necesario.")
                    st.rerun()
        ocr_cli = st.session_state.get("cli_ocr", {})
        if ocr_cli:
            with st.expander("📋 Datos extraídos por la IA", expanded=True):
                c1x, c2x, c3x = st.columns(3)
                c1x.metric("Cliente", ocr_cli.get("nombre") or "—")
                c2x.metric("Monto", f"{ocr_cli.get('monto') or 0:,.2f} {ocr_cli.get('moneda','GTQ')}")
                c3x.metric("N° Factura", ocr_cli.get("numero_factura") or "—")

    _def_cli   = _safe(ocr_cli.get("nombre", ""))
    _def_fac_c = _safe(ocr_cli.get("numero_factura", ""))
    _def_mnt_c = float(ocr_cli.get("monto") or 0.0)
    _def_obs_c = _safe(ocr_cli.get("descripcion", ""))
    try:
        _def_fv_c  = pd.Timestamp(ocr_cli["fecha_vencimiento"]).date() if ocr_cli.get("fecha_vencimiento") else datetime.date.today() + datetime.timedelta(days=30)
        _def_fe_c  = pd.Timestamp(ocr_cli["fecha_emision"]).date()     if ocr_cli.get("fecha_emision")     else datetime.date.today()
    except Exception:
        _def_fv_c = datetime.date.today() + datetime.timedelta(days=30)
        _def_fe_c = datetime.date.today()

    with st.form("form_nueva_cli", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            cliente = st.text_input("Cliente *", value=_def_cli, placeholder="Ej. Ministerio de Salud GT")
        with c2:
            pais = st.selectbox("País", PAISES, index=PAISES.index("GUATEMALA"))

        c3, c4 = st.columns(2)
        with c3:
            num_factura = st.text_input("N° Factura *", value=_def_fac_c, placeholder="FAC-2026-001")
        with c4:
            monto_gtq = st.number_input("Monto GTQ *", min_value=0.0, value=_def_mnt_c, step=100.0, format="%.2f")

        c5, c6, c7 = st.columns(3)
        with c5:
            monto_usd = st.number_input("Equivalente USD", min_value=0.0, value=0.0, step=10.0, format="%.2f")
        with c6:
            fecha_emision = st.date_input("Fecha de emisión *", value=_def_fe_c)
        with c7:
            fecha_venc = st.date_input("Fecha de vencimiento *", value=_def_fv_c)

        obs = st.text_area("Observaciones / Referencia", value=_def_obs_c, placeholder="Ej. Proyecto X, contrato 2026-12...", height=70)
        sub = st.form_submit_button("💾 Guardar", type="primary", use_container_width=True)

        if sub:
            if not cliente.strip():
                st.error("El cliente es obligatorio.")
            elif not num_factura.strip():
                st.error("El número de factura es obligatorio.")
            elif monto_gtq <= 0:
                st.error("El monto debe ser mayor a 0.")
            else:
                data = {
                    "cliente":           cliente.strip().upper(),
                    "pais":              pais,
                    "numero_factura":    num_factura.strip().upper(),
                    "monto_local":       monto_gtq,
                    "moneda":            "GTQ",
                    "monto_usd":         monto_usd,
                    "fecha_emision":     fecha_emision,
                    "fecha_vencimiento": fecha_venc,
                    "estado":            "PENDIENTE",
                    "observaciones":     obs.strip() or None,
                    "fecha_carga":       datetime.datetime.now().isoformat(),
                }
                ok = add_cliente_cc(data)
                if ok:
                    st.session_state.pop("cli_ocr", None)
                    st.success("✅ Factura registrada correctamente.")
                    st.rerun()
                else:
                    st.error("❌ Error al guardar. Verificá que las tablas existan en Supabase (ver setup_cuenta_corriente.sql).")


def _cli_registrar_cobro(df, hoy):
    st.markdown("### Registrar cobro de factura")

    if df.empty:
        st.info("No hay facturas registradas.")
        return

    df_pend = df[df["_ev"].isin(["PENDIENTE", "VENCIDA"])].copy()
    if df_pend.empty:
        st.success("✅ No hay facturas pendientes de cobro. ¡Todo al día!")
        return

    options = []
    mapping = {}
    for _, row in df_pend.sort_values("fecha_vencimiento").iterrows():
        tag   = "[VENCIDA] " if row["_ev"] == "VENCIDA" else ""
        fac   = _safe(row.get("numero_factura")) or "S/N"
        monto = float(row.get("monto_local") or 0)
        label = tag + _safe(row.get("cliente")) + " · " + fac + " · Q " + f"{monto:,.2f}" + " · Vence " + _fmt_date(row.get("fecha_vencimiento"))
        options.append(label)
        mapping[label] = row

    sel       = st.selectbox("Seleccionar factura a cobrar", options, key="cli_cobro_sel")
    row       = mapping[sel]
    ev        = row["_ev"]
    monto_sel = float(row.get("monto_local") or 0)

    st.markdown(
        "<div style='background:#1A1F2E;border-radius:8px;padding:.7rem 1rem;"
        "border:1px solid " + _border_color(ev) + ";margin:.5rem 0 1rem 0;font-size:.85rem;'>"
        "<b>Cliente:</b> " + _safe(row.get("cliente")) +
        " &nbsp;|&nbsp; <b>Monto:</b> Q " + f"{monto_sel:,.2f}" +
        " &nbsp;|&nbsp; <b>Vencimiento:</b> " + _fmt_date(row.get("fecha_vencimiento")) +
        " &nbsp;" + _badge(ev) + "</div>",
        unsafe_allow_html=True
    )

    c1, c2 = st.columns(2)
    with c1:
        fecha_cobro = st.date_input("Fecha de cobro *", value=datetime.date.today(), key="cli_fecha_cobro")
    with c2:
        nro_ref = st.text_input("N° Referencia / Transferencia", placeholder="TRF-2026-00456", key="cli_nro_ref")

    if st.button("✅ Confirmar Cobro", type="primary", use_container_width=True, key="cli_confirm_cobro"):
        ok = update_cliente_cc(int(row["id"]), {
            "estado":            "COBRADA",
            "fecha_cobro":       fecha_cobro,
            "numero_referencia": nro_ref.strip().upper() or None,
        })
        if ok:
            st.success("✅ Cobro registrado para **" + _safe(row.get("cliente")) + "** — Q " + f"{monto_sel:,.2f}")
            st.rerun()
        else:
            st.error("❌ Error al registrar el cobro.")


def _cli_editar(df, hoy):
    st.markdown("### Editar o eliminar factura de cliente")

    if df.empty:
        st.info("No hay facturas para editar.")
        return

    options = []
    mapping = {}
    for _, row in df.sort_values("fecha_vencimiento", ascending=False).iterrows():
        fac   = _safe(row.get("numero_factura")) or "S/N"
        monto = float(row.get("monto_local") or 0)
        label = "[" + row["_ev"] + "] " + _safe(row.get("cliente")) + " · " + fac + " · Q " + f"{monto:,.2f}"
        options.append(label)
        mapping[label] = row

    sel = st.selectbox("Seleccionar registro", options, key="cli_edit_sel")
    row = mapping[sel]

    with st.form("form_edit_cli"):
        c1, c2 = st.columns(2)
        with c1:
            edit_cli = st.text_input("Cliente", value=_safe(row.get("cliente")))
        with c2:
            pais_val  = _safe(row.get("pais"))
            edit_pais = st.selectbox("País", PAISES, index=PAISES.index(pais_val) if pais_val in PAISES else 0)

        c3, c4 = st.columns(2)
        with c3:
            edit_fac   = st.text_input("N° Factura", value=_safe(row.get("numero_factura")))
        with c4:
            edit_monto = st.number_input("Monto GTQ", min_value=0.0, value=float(row.get("monto_local") or 0), step=100.0, format="%.2f")

        c5, c6 = st.columns(2)
        with c5:
            fv_val  = row.get("fecha_vencimiento")
            fv_def  = fv_val.date() if pd.notna(fv_val) and hasattr(fv_val, "date") else datetime.date.today()
            edit_fv = st.date_input("Vencimiento", value=fv_def)
        with c6:
            est_opts = ["PENDIENTE", "COBRADA"]
            est_val  = _safe(row.get("estado"))
            edit_est = st.selectbox("Estado", est_opts, index=est_opts.index(est_val) if est_val in est_opts else 0)

        edit_obs = st.text_area("Observaciones", value=_safe(row.get("observaciones")), height=60)

        btn1, btn2 = st.columns(2)
        with btn1:
            save_ok = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)
        with btn2:
            del_req = st.form_submit_button("🗑️ Eliminar", type="secondary", use_container_width=True)

    if save_ok:
        ok = update_cliente_cc(int(row["id"]), {
            "cliente":           edit_cli.strip().upper(),
            "pais":              edit_pais,
            "numero_factura":    edit_fac.strip().upper() or None,
            "monto_local":       edit_monto,
            "fecha_vencimiento": edit_fv,
            "estado":            edit_est,
            "observaciones":     edit_obs.strip() or None,
        })
        if ok:
            st.success("✅ Registro actualizado.")
            st.rerun()
        else:
            st.error("❌ Error al guardar cambios.")

    if del_req:
        st.session_state["cli_pending_del"] = int(row["id"])

    if st.session_state.get("cli_pending_del"):
        st.markdown("---")
        st.warning("⚠️ **¿Confirmás la eliminación permanente de:** `" + sel + "`")
        dc1, dc2 = st.columns(2)
        with dc1:
            if st.button("🚨 SÍ, ELIMINAR", type="primary", use_container_width=True, key="cli_del_confirm"):
                ok = delete_cliente_cc(st.session_state["cli_pending_del"])
                if ok:
                    st.success("✅ Eliminado.")
                    del st.session_state["cli_pending_del"]
                    st.rerun()
                else:
                    st.error("❌ Error al eliminar.")
        with dc2:
            if st.button("Cancelar", use_container_width=True, key="cli_del_cancel"):
                del st.session_state["cli_pending_del"]
                st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# ALERTAS & COBRANZA
# ═════════════════════════════════════════════════════════════════════════════

def _estado_alerta(row, hoy, dias_prev, dias_crit):
    """Devuelve (estado, dias) donde estado = CRITICA|PREVENTIVA|VIGENTE|COBRADA"""
    if row.get("estado") == "COBRADA":
        return "COBRADA", 0
    fv = row.get("fecha_vencimiento")
    if not pd.notna(fv):
        return "VIGENTE", 0
    dias_al_venc = (pd.Timestamp(fv).date() - hoy).days
    if dias_al_venc < -dias_crit:
        return "CRITICA", abs(dias_al_venc)
    elif dias_al_venc <= dias_prev:
        return "PREVENTIVA", dias_al_venc
    return "VIGENTE", dias_al_venc


def _html_base(titulo, subtitulo, kpis_html, secciones_html, fecha_str):
    return f"""
    <html><body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:20px;margin:0;">
    <div style="max-width:680px;margin:0 auto;background:white;border-radius:10px;
        overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.1);">
        <div style="background:linear-gradient(90deg,#0F4C81 0%,#4B9CD3 100%);padding:20px 28px;">
            <div style="font-size:1.1rem;font-weight:800;color:white;">🏦 {titulo}</div>
            <div style="font-size:.82rem;color:rgba(255,255,255,.75);margin-top:3px;">{subtitulo} · Corte {fecha_str}</div>
        </div>
        <div style="padding:24px 28px;">
            <p style="color:#333;margin-top:0;">Dirección,</p>
            <p style="color:#555;font-size:.88rem;">Se adjunta el estado al día de la fecha. A continuación el detalle del período.</p>
            <div style="display:flex;gap:12px;margin:20px 0;">{kpis_html}</div>
            {secciones_html}
            <p style="font-size:.72rem;color:#aaa;border-top:1px solid #eee;padding-top:14px;margin-top:24px;margin-bottom:0;">
                Generado automáticamente · PROA Consulting · {fecha_str}
            </p>
        </div>
    </div>
    </body></html>"""


def _html_tabla(df_in, cols):
    rows = ""
    for _, r in df_in.iterrows():
        cells = "".join(f"<td style='padding:7px 8px;'>{v(r)}</td>" for _, v in cols)
        rows += f"<tr style='border-bottom:1px solid #eee;'>{cells}</tr>"
    headers = "".join(f"<th style='padding:7px 8px;text-align:left;'>{h}</th>" for h, _ in cols)
    return (
        f"<table style='width:100%;border-collapse:collapse;font-size:.82rem;margin-bottom:16px;'>"
        f"<thead><tr style='background:#f0f4ff;color:#555;font-size:.75rem;'>{headers}</tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _generar_html_email(df_crit, df_prev, resumen):
    mes  = datetime.date.today().strftime("%B %Y")
    fecha_str = datetime.date.today().strftime("%d/%m/%Y")

    def _tabla_rows(df_in):
        rows = ""
        for _, r in df_in.iterrows():
            rows += (
                "<tr style='border-bottom:1px solid #eee;'>"
                f"<td style='padding:7px 8px;'>{_safe(r.get('cliente'))}</td>"
                f"<td style='padding:7px 8px;text-align:center;'>{_fmt_date(r.get('fecha_emision'))}</td>"
                f"<td style='padding:7px 8px;text-align:center;'>{_fmt_date(r.get('fecha_vencimiento'))}</td>"
                f"<td style='padding:7px 8px;text-align:right;font-weight:700;'>Q {float(r.get('monto_local') or 0):,.2f}</td>"
                f"<td style='padding:7px 8px;text-align:center;'>{_safe(r.get('numero_factura')) or 'S/N'}</td>"
                "</tr>"
            )
        return rows

    seccion_crit = ""
    if not df_crit.empty:
        seccion_crit = f"""
        <h3 style="color:#C62828;font-size:.82rem;text-transform:uppercase;
            border-bottom:2px solid #ffcdd2;padding-bottom:5px;margin-top:24px;">
            🔴 Vencidas — Requieren acción inmediata ({len(df_crit)})
        </h3>
        <table style="width:100%;border-collapse:collapse;font-size:.82rem;">
            <thead><tr style="background:#ffebee;color:#555;font-size:.75rem;">
                <th style="padding:7px 8px;text-align:left;">Cliente</th>
                <th style="padding:7px 8px;">F. Emisión</th>
                <th style="padding:7px 8px;">Vencimiento</th>
                <th style="padding:7px 8px;text-align:right;">Monto</th>
                <th style="padding:7px 8px;">N° Factura</th>
            </tr></thead>
            <tbody>{_tabla_rows(df_crit)}</tbody>
        </table>
        <p style="font-size:.78rem;color:#C62828;margin-top:6px;">
            Requiere acción inmediata. Se solicita confirmación de Dirección para iniciar gestión de cobro.
        </p>"""

    seccion_prev = ""
    if not df_prev.empty:
        seccion_prev = f"""
        <h3 style="color:#E65100;font-size:.82rem;text-transform:uppercase;
            border-bottom:2px solid #ffe0b2;padding-bottom:5px;margin-top:24px;">
            ⚠️ Próximas a vencer — Acción preventiva ({len(df_prev)})
        </h3>
        <table style="width:100%;border-collapse:collapse;font-size:.82rem;">
            <thead><tr style="background:#fff8e1;color:#555;font-size:.75rem;">
                <th style="padding:7px 8px;text-align:left;">Cliente</th>
                <th style="padding:7px 8px;">F. Emisión</th>
                <th style="padding:7px 8px;">Vencimiento</th>
                <th style="padding:7px 8px;text-align:right;">Monto</th>
                <th style="padding:7px 8px;">N° Factura</th>
            </tr></thead>
            <tbody>{_tabla_rows(df_prev)}</tbody>
        </table>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:20px;margin:0;">
    <div style="max-width:680px;margin:0 auto;background:white;border-radius:10px;
        overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.1);">
        <div style="background:linear-gradient(90deg,#0F4C81 0%,#4B9CD3 100%);padding:20px 28px;">
            <div style="font-size:1.1rem;font-weight:800;color:white;">🏦 Cuenta Corriente — PROA Consulting</div>
            <div style="font-size:.82rem;color:rgba(255,255,255,.75);margin-top:3px;">
                Informe de cobranza · Corte {fecha_str}
            </div>
        </div>
        <div style="padding:24px 28px;">
            <p style="color:#333;margin-top:0;">Dirección,</p>
            <p style="color:#555;font-size:.88rem;">
                Se adjunta el estado de cuentas corrientes al día de la fecha.
                A continuación el detalle del período.
            </p>
            <div style="display:flex;gap:12px;margin:20px 0;">
                <div style="flex:1;background:#f0f4ff;border-radius:6px;padding:14px;text-align:center;">
                    <div style="font-size:.7rem;color:#888;text-transform:uppercase;margin-bottom:4px;">Pendiente total</div>
                    <div style="font-size:1.3rem;font-weight:800;color:#1565C0;">Q {resumen['total_pend']:,.2f}</div>
                </div>
                <div style="flex:1;background:#fff3f3;border-radius:6px;padding:14px;text-align:center;">
                    <div style="font-size:.7rem;color:#888;text-transform:uppercase;margin-bottom:4px;">Críticas</div>
                    <div style="font-size:1.3rem;font-weight:800;color:#C62828;">{resumen['n_criticas']}</div>
                </div>
                <div style="flex:1;background:#fffde7;border-radius:6px;padding:14px;text-align:center;">
                    <div style="font-size:.7rem;color:#888;text-transform:uppercase;margin-bottom:4px;">Preventivas</div>
                    <div style="font-size:1.3rem;font-weight:800;color:#E65100;">{resumen['n_prev']}</div>
                </div>
            </div>
            {seccion_crit}
            {seccion_prev}
            <p style="font-size:.72rem;color:#aaa;border-top:1px solid #eee;
                padding-top:14px;margin-top:24px;margin-bottom:0;">
                Generado automáticamente por el sistema de Cuenta Corriente · PROA Consulting · {fecha_str}
            </p>
        </div>
    </div>
    </body></html>"""


def _generar_html_email_proveedores(df_crit, df_prev, df_tarde, resumen):
    fecha_str = datetime.date.today().strftime("%d/%m/%Y")
    cols = [
        ("Proveedor",    lambda r: _safe(r.get("proveedor"))),
        ("N° Factura",   lambda r: _safe(r.get("numero_factura")) or "S/N"),
        ("Vencimiento",  lambda r: _fmt_date(r.get("fecha_vencimiento"))),
        ("Monto",        lambda r: f"Q {float(r.get('monto_local') or 0):,.2f}"),
    ]
    cols_tarde = [
        ("Proveedor",    lambda r: _safe(r.get("proveedor"))),
        ("N° Factura",   lambda r: _safe(r.get("numero_factura")) or "S/N"),
        ("Vto.",         lambda r: _fmt_date(r.get("fecha_vencimiento"))),
        ("F. Pago",      lambda r: _fmt_date(r.get("fecha_pago"))),
        ("Días tardío",  lambda r: str(r.get("_dias_tarde", 0))),
        ("Monto",        lambda r: f"Q {float(r.get('monto_local') or 0):,.2f}"),
    ]
    sec_crit = ""
    if not df_crit.empty:
        sec_crit = (
            "<h3 style='color:#C62828;font-size:.82rem;text-transform:uppercase;"
            "border-bottom:2px solid #ffcdd2;padding-bottom:5px;margin-top:24px;'>"
            f"🔴 Pagos vencidos — Atención inmediata ({len(df_crit)})</h3>"
            + _html_tabla(df_crit, cols)
        )
    sec_prev = ""
    if not df_prev.empty:
        sec_prev = (
            "<h3 style='color:#E65100;font-size:.82rem;text-transform:uppercase;"
            "border-bottom:2px solid #ffe0b2;padding-bottom:5px;margin-top:24px;'>"
            f"⚠️ Próximos a vencer ({len(df_prev)})</h3>"
            + _html_tabla(df_prev, cols)
        )
    sec_tarde = ""
    if not df_tarde.empty:
        sec_tarde = (
            "<h3 style='color:#6A1B9A;font-size:.82rem;text-transform:uppercase;"
            "border-bottom:2px solid #e1bee7;padding-bottom:5px;margin-top:24px;'>"
            f"📊 Desvíos — Pagados fuera de término ({len(df_tarde)})</h3>"
            + _html_tabla(df_tarde, cols_tarde)
        )
    kpis = (
        f"<div style='flex:1;background:#fff3f3;border-radius:6px;padding:14px;text-align:center;'>"
        f"<div style='font-size:.7rem;color:#888;text-transform:uppercase;margin-bottom:4px;'>Vencidas a pagar</div>"
        f"<div style='font-size:1.3rem;font-weight:800;color:#C62828;'>{resumen['n_criticas']}</div></div>"
        f"<div style='flex:1;background:#f0f4ff;border-radius:6px;padding:14px;text-align:center;'>"
        f"<div style='font-size:.7rem;color:#888;text-transform:uppercase;margin-bottom:4px;'>Total pendiente</div>"
        f"<div style='font-size:1.3rem;font-weight:800;color:#1565C0;'>Q {resumen['total_pend']:,.2f}</div></div>"
        f"<div style='flex:1;background:#fffde7;border-radius:6px;padding:14px;text-align:center;'>"
        f"<div style='font-size:.7rem;color:#888;text-transform:uppercase;margin-bottom:4px;'>Preventivas</div>"
        f"<div style='font-size:1.3rem;font-weight:800;color:#E65100;'>{resumen['n_prev']}</div></div>"
        f"<div style='flex:1;background:#f3e5f5;border-radius:6px;padding:14px;text-align:center;'>"
        f"<div style='font-size:.7rem;color:#888;text-transform:uppercase;margin-bottom:4px;'>Desvíos</div>"
        f"<div style='font-size:1.3rem;font-weight:800;color:#6A1B9A;'>{resumen['n_tarde']}</div></div>"
    )
    return _html_base(
        "Cuenta Corriente — Pagos a Proveedores",
        "Informe de egresos y desvíos",
        kpis, sec_crit + sec_prev + sec_tarde, fecha_str
    )


def _enviar_email(html_content, destinatarios):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    try:
        cfg = st.secrets.get("email", {})
        if not cfg:
            return False, (
                "No hay configuración de email. Agregá en Streamlit Cloud → Settings → Secrets:\n"
                "[email]\nsmtp_server = \"smtp.gmail.com\"\nsmtp_port = 587\n"
                "username = \"tu@email.com\"\npassword = \"tu_app_password\""
            )
        smtp_server = cfg.get("smtp_server", "smtp.gmail.com")
        smtp_port   = int(cfg.get("smtp_port", 587))
        username    = cfg.get("username", "")
        password    = cfg.get("password", "")
        from_addr   = cfg.get("from_address", username)
        if not username or not password:
            return False, "Falta username o password en la sección [email] de Secrets."
        mes = datetime.date.today().strftime("%B %Y")
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Informe Cuentas Corrientes — {mes}"
        msg["From"]    = from_addr
        msg["To"]      = ", ".join(destinatarios)
        msg.attach(MIMEText(html_content, "html", "utf-8"))
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(username, password)
            server.sendmail(from_addr, destinatarios, msg.as_string())
        return True, "OK"
    except Exception as e:
        return False, str(e)


def _render_alertas(pais_sel, theme_color):
    hoy = datetime.date.today()
    tab_cli_a, tab_prov_a = st.tabs(["📤 Cobros — Clientes", "📥 Pagos — Proveedores"])
    with tab_cli_a:
        _render_alertas_clientes(pais_sel, theme_color, hoy)
    with tab_prov_a:
        _render_alertas_proveedores(pais_sel, theme_color, hoy)


def _render_alertas_clientes(pais_sel, theme_color, hoy):
    df  = get_clientes_cc()
    if not df.empty and pais_sel != "TODOS" and "pais" in df.columns:
        df = df[df["pais"] == pais_sel].copy()

    # ── Configuración ────────────────────────────────────────────────────────
    with st.expander("⚙️ Configuración de alertas y destinatarios", expanded=False):
        st.markdown("**Timeline de alertas**")
        cc1, cc2 = st.columns(2)
        with cc1:
            dias_prev = st.number_input(
                "Días antes del vencimiento → aviso preventivo",
                min_value=0, max_value=90,
                value=st.session_state.get("alerta_dias_prev", 5),
                key="alerta_dias_prev_w"
            )
            st.session_state["alerta_dias_prev"] = dias_prev
        with cc2:
            dias_crit = st.number_input(
                "Días DESPUÉS del vencimiento → alarma crítica",
                min_value=0, max_value=90,
                value=st.session_state.get("alerta_dias_crit", 0),
                help="0 = crítica desde el mismo día del vencimiento",
                key="alerta_dias_crit_w"
            )
            st.session_state["alerta_dias_crit"] = dias_crit

        st.markdown("")
        st.markdown("**📧 Destinatarios del informe** (uno por línea)")
        dest_text = st.text_area(
            "Destinatarios",
            value=st.session_state.get("alerta_destinatarios", "falcaraz@proaconsulting.com.ar"),
            height=90,
            key="alerta_dest_w",
            label_visibility="collapsed",
            placeholder="correo1@empresa.com\ncorreo2@empresa.com"
        )
        st.session_state["alerta_destinatarios"] = dest_text

        # Instrucciones email
        with st.expander("🔧 Configurar envío de email (SMTP)", expanded=False):
            st.markdown("""
Para habilitar el envío real de emails, agregá esto en **Streamlit Cloud → Settings → Secrets**:
```toml
[email]
smtp_server   = "smtp.gmail.com"
smtp_port     = 587
username      = "tu@email.com"
password      = "tu_app_password"
from_address  = "tu@email.com"
```
Si usás Gmail, generá una **App Password** en myaccount.google.com → Seguridad → Contraseñas de aplicación.
            """)

    dias_prev = st.session_state.get("alerta_dias_prev", 5)
    dias_crit = st.session_state.get("alerta_dias_crit", 0)
    dest_text = st.session_state.get("alerta_destinatarios", "falcaraz@proaconsulting.com.ar")

    # ── Datos de ejemplo para preview/test ───────────────────────────────────
    hoy_ts = pd.Timestamp(hoy)
    _demo = pd.DataFrame([
        {"cliente": "UNICEF Guatemala",       "numero_factura": "GT-2026-APR-02", "monto_local": 11750.0,
         "fecha_emision": hoy_ts - pd.Timedelta(days=22), "fecha_vencimiento": hoy_ts - pd.Timedelta(days=18),
         "estado": "PENDIENTE", "observaciones": "Segundo período consecutivo con retraso"},
        {"cliente": "Special Olympics Chile", "numero_factura": "CL-2026-APR-01", "monto_local": 22170.0,
         "fecha_emision": hoy_ts - pd.Timedelta(days=22), "fecha_vencimiento": hoy_ts - pd.Timedelta(days=18),
         "estado": "PENDIENTE", "observaciones": "Supera umbral de política de cobro"},
        {"cliente": "UNICEF Paraguay",        "numero_factura": "PY-2026-MAY-01", "monto_local": 248000.0,
         "fecha_emision": hoy_ts - pd.Timedelta(days=10), "fecha_vencimiento": hoy_ts + pd.Timedelta(days=4),
         "estado": "PENDIENTE", "observaciones": "Mayor factura del período activo"},
        {"cliente": "UNICEF Bolivia",         "numero_factura": "BO-2026-MAY-01", "monto_local": 58000.0,
         "fecha_emision": hoy_ts - pd.Timedelta(days=10), "fecha_vencimiento": hoy_ts + pd.Timedelta(days=4),
         "estado": "PENDIENTE", "observaciones": ""},
    ])
    _demo["_alerta_est"]  = [_estado_alerta(r, hoy, dias_prev, dias_crit)[0] for _, r in _demo.iterrows()]
    _demo["_alerta_dias"] = [_estado_alerta(r, hoy, dias_prev, dias_crit)[1] for _, r in _demo.iterrows()]
    _demo_crit = _demo[_demo["_alerta_est"] == "CRITICA"]
    _demo_prev = _demo[_demo["_alerta_est"] == "PREVENTIVA"]
    _demo_resumen = {
        "total_pend": _demo["monto_local"].sum(),
        "n_criticas": len(_demo_crit),
        "n_prev":     len(_demo_prev),
    }

    # ── Botones preview / test email ──────────────────────────────────────────
    col_prev, col_test, _ = st.columns([1, 1, 2])
    with col_prev:
        mostrar_preview = st.toggle("👁 Ver preview email", key="toggle_preview_email")
    with col_test:
        if st.button("📧 Enviar email de prueba", key="btn_test_email"):
            dests = [d.strip() for d in dest_text.strip().splitlines() if d.strip()]
            if not dests:
                st.error("Agregá al menos un destinatario.")
            else:
                html_test = _generar_html_email(_demo_crit, _demo_prev, _demo_resumen)
                with st.spinner("Enviando email de prueba..."):
                    ok, msg = _enviar_email(html_test, dests)
                if ok:
                    st.success(f"✅ Email de prueba enviado a: {', '.join(dests)}")
                else:
                    st.error(f"❌ {msg}")

    if mostrar_preview:
        html_preview = _generar_html_email(_demo_crit, _demo_prev, _demo_resumen)
        with st.expander("📄 Vista previa del email (datos de ejemplo)", expanded=True):
            st.components.v1.html(html_preview, height=650, scrolling=True)
        st.markdown("")

    # ── Calcular estados ─────────────────────────────────────────────────────
    if df.empty:
        st.info("💡 No hay facturas cargadas aún. El preview de arriba muestra cómo se verá cuando haya datos.")
        return

    resultados = [_estado_alerta(row, hoy, dias_prev, dias_crit) for _, row in df.iterrows()]
    df["_alerta_est"]  = [r[0] for r in resultados]
    df["_alerta_dias"] = [r[1] for r in resultados]

    df_crit = df[df["_alerta_est"] == "CRITICA"].sort_values("_alerta_dias", ascending=False)
    df_prev = df[df["_alerta_est"] == "PREVENTIVA"].sort_values("_alerta_dias")
    df_cob  = df[df["_alerta_est"] == "COBRADA"]

    total_pend = df[df["_alerta_est"].isin(["CRITICA","PREVENTIVA","VIGENTE"])]["monto_local"].sum()
    total_crit = df_crit["monto_local"].sum() if not df_crit.empty else 0

    # ── KPIs ─────────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    _kpi_card(c1, "Críticas sin cobrar",  str(len(df_crit)),    f"Q {total_crit:,.2f}",   C_DANGER)
    _kpi_card(c2, "Pendiente total",      f"Q {total_pend:,.2f}", f"{len(df_crit)+len(df_prev)} alertas", C_WARNING)
    _kpi_card(c3, "Alertas preventivas",  str(len(df_prev)),    "próximas a vencer",      theme_color)
    _kpi_card(c4, "Cobradas",             str(len(df_cob)),     f"Q {df_cob['monto_local'].sum() if not df_cob.empty else 0:,.2f}", C_SUCCESS)

    st.markdown("")

    # ── Timeline visual ───────────────────────────────────────────────────────
    st.markdown(
        f"<div style='background:#1A1F2E;border:1px solid #2D3348;border-radius:10px;"
        "padding:.8rem 1.4rem;margin-bottom:1rem;display:flex;align-items:center;gap:0;'>"
        "<div style='flex:1;text-align:center;font-size:.72rem;color:#6B7280;'>📄 Fecha factura<br><b style='color:#A0A4B8;'>Día 0</b></div>"
        "<div style='flex:2;height:4px;background:linear-gradient(90deg,#2D3348,#2D3348);border-radius:2px;position:relative;'>"
        f"<div style='position:absolute;top:-18px;left:{min(dias_prev*5,70)}%;font-size:.65rem;color:{theme_color};white-space:nowrap;'>Día {dias_prev} →</div>"
        f"<div style='position:absolute;top:0;left:{min(dias_prev*5,70)}%;width:10px;height:10px;background:{theme_color};"
        "border-radius:50%;transform:translate(-50%,-3px);'></div>"
        "</div>"
        f"<div style='flex:1;text-align:center;font-size:.72rem;color:{theme_color};'>"
        f"⚠️ Aviso preventivo<br><b>Día {dias_prev}</b></div>"
        "<div style='flex:2;height:4px;background:linear-gradient(90deg,#2D3348,#2D3348);border-radius:2px;'></div>"
        f"<div style='flex:1;text-align:center;font-size:.72rem;color:{C_DANGER};'>"
        f"🔴 Alarma crítica<br><b>Día {dias_crit} post-venc.</b></div>"
        "</div>",
        unsafe_allow_html=True
    )

    # ── Críticas ──────────────────────────────────────────────────────────────
    if not df_crit.empty:
        st.markdown(
            f"<div style='color:{C_DANGER};font-weight:700;font-size:.78rem;letter-spacing:1px;"
            "text-transform:uppercase;margin:.8rem 0 .4rem;'>🚨 Requiere atención inmediata</div>",
            unsafe_allow_html=True
        )
        for _, row in df_crit.iterrows():
            mora  = int(row["_alerta_dias"])
            monto = float(row.get("monto_local") or 0)
            fac   = _safe(row.get("numero_factura")) or "S/N"
            obs   = _safe(row.get("observaciones"))
            st.markdown(
                f"<div style='background:linear-gradient(135deg,{C_DANGER}15 0%,#1A1F2E 100%);"
                f"border-left:4px solid {C_DANGER};border-radius:8px;padding:.8rem 1.1rem;margin-bottom:.4rem;'>"
                "<div style='display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;'>"
                "<div style='flex:1;'>"
                f"<div style='font-weight:700;color:#FAFAFA;font-size:.95rem;'>"
                f"Factura vencida hace {mora} día{'s' if mora!=1 else ''} — {_safe(row.get('cliente'))}</div>"
                f"<div style='font-size:.75rem;color:#A0A4B8;margin-top:3px;'>"
                f"<b>{fac}</b> · Q {monto:,.2f} · Vencía: <b>{_fmt_date(row.get('fecha_vencimiento'))}</b>"
                + (f" · 📝 {obs}" if obs else "") + "</div>"
                f"<div style='margin-top:5px;'>"
                f"<span style='background:{C_DANGER}25;color:{C_DANGER};font-size:.7rem;font-weight:700;"
                f"padding:2px 10px;border-radius:12px;border:1px solid {C_DANGER}44;'>🔴 Crítico · {mora}d mora</span>"
                "</div></div>"
                f"<div style='font-weight:800;color:{C_DANGER};font-size:1rem;white-space:nowrap;'>Q {monto:,.2f}</div>"
                "</div></div>",
                unsafe_allow_html=True
            )

    # ── Preventivas ───────────────────────────────────────────────────────────
    if not df_prev.empty:
        st.markdown(
            f"<div style='color:{C_WARNING};font-weight:700;font-size:.78rem;letter-spacing:1px;"
            "text-transform:uppercase;margin:1rem 0 .4rem;'>⚠️ Preventivas — Próximos vencimientos</div>",
            unsafe_allow_html=True
        )
        for _, row in df_prev.iterrows():
            dias_r = int(row["_alerta_dias"])
            monto  = float(row.get("monto_local") or 0)
            fac    = _safe(row.get("numero_factura")) or "S/N"
            label  = "vence hoy" if dias_r == 0 else (f"vence en {dias_r} día{'s' if dias_r!=1 else ''}" if dias_r > 0 else f"venció hace {abs(dias_r)}d")
            st.markdown(
                f"<div style='background:linear-gradient(135deg,{C_WARNING}12 0%,#1A1F2E 100%);"
                f"border-left:4px solid {C_WARNING};border-radius:8px;padding:.8rem 1.1rem;margin-bottom:.4rem;'>"
                "<div style='display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;'>"
                "<div style='flex:1;'>"
                f"<div style='font-weight:700;color:#FAFAFA;font-size:.95rem;'>"
                f"{_safe(row.get('cliente'))} — {label}</div>"
                f"<div style='font-size:.75rem;color:#A0A4B8;margin-top:3px;'>"
                f"<b>{fac}</b> · Q {monto:,.2f} · Venc: <b>{_fmt_date(row.get('fecha_vencimiento'))}</b></div>"
                f"<div style='margin-top:5px;'>"
                f"<span style='background:{C_WARNING}25;color:{C_WARNING};font-size:.7rem;font-weight:700;"
                f"padding:2px 10px;border-radius:12px;border:1px solid {C_WARNING}44;'>⚠️ Preventiva</span>"
                "</div></div>"
                f"<div style='font-weight:800;color:{C_WARNING};font-size:1rem;white-space:nowrap;'>Q {monto:,.2f}</div>"
                "</div></div>",
                unsafe_allow_html=True
            )

    if df_crit.empty and df_prev.empty:
        st.markdown(
            f"<div style='background:{C_SUCCESS}12;border:1px solid {C_SUCCESS}44;border-radius:10px;"
            "padding:1.5rem;text-align:center;margin-top:1rem;'>"
            "<div style='font-size:2rem;'>✅</div>"
            f"<div style='color:{C_SUCCESS};font-weight:700;font-size:1rem;'>Todo al día — sin alertas activas</div>"
            "<div style='color:#A0A4B8;font-size:.8rem;margin-top:4px;'>No hay facturas críticas ni preventivas pendientes.</div>"
            "</div>",
            unsafe_allow_html=True
        )
        return

    # ── Email ─────────────────────────────────────────────────────────────────
    st.markdown("---")
    col_btn, col_info = st.columns([1, 2])
    with col_btn:
        if st.button("📧 Enviar informe por email", type="primary", use_container_width=True, key="btn_email_alertas"):
            destinatarios = [d.strip() for d in dest_text.strip().splitlines() if d.strip()]
            if not destinatarios:
                st.error("Agregá al menos un destinatario en la configuración.")
            else:
                html_email = _generar_html_email(df_crit, df_prev, {
                    "total_pend": total_pend,
                    "n_criticas": len(df_crit),
                    "n_prev":     len(df_prev),
                })
                with st.spinner("Enviando..."):
                    ok, msg = _enviar_email(html_email, destinatarios)
                if ok:
                    st.success(f"✅ Informe enviado a: {', '.join(destinatarios)}")
                else:
                    st.error(f"❌ {msg}")
    with col_info:
        dests = [d.strip() for d in dest_text.strip().splitlines() if d.strip()]
        st.caption("📧 Destinatarios: " + " · ".join(dests) if dests else "Sin destinatarios configurados")


def _render_alertas_proveedores(pais_sel, theme_color, hoy):
    df = get_proveedores_cc()
    if not df.empty and pais_sel != "TODOS" and "pais" in df.columns:
        df = df[df["pais"] == pais_sel].copy()

    dias_prev = st.session_state.get("alerta_dias_prev", 5)
    dias_crit = st.session_state.get("alerta_dias_crit", 0)
    dest_text = st.session_state.get("alerta_destinatarios", "falcaraz@proaconsulting.com.ar")

    if df.empty:
        st.info("No hay facturas de proveedores registradas.")
        return

    df["_ev"] = df.apply(lambda r: _estado_visual_prov(r, hoy), axis=1)
    resultados_p = [_estado_alerta(row, hoy, dias_prev, dias_crit) for _, row in df.iterrows()]
    df["_alerta_est"]  = [r[0] for r in resultados_p]
    df["_alerta_dias"] = [r[1] for r in resultados_p]

    df_crit_p = df[df["_alerta_est"] == "CRITICA"].sort_values("_alerta_dias", ascending=False)
    df_prev_p = df[df["_alerta_est"] == "PREVENTIVA"].sort_values("_alerta_dias")

    # Desvíos: pagadas después de vencimiento
    df_pag = df[df["_ev"] == "PAGADA"].copy()
    df_tarde = pd.DataFrame()
    if not df_pag.empty:
        df_pag2 = df_pag[df_pag["fecha_pago"].notna() & df_pag["fecha_vencimiento"].notna()].copy()
        if not df_pag2.empty:
            df_pag2["_dias_tarde"] = df_pag2.apply(
                lambda r: max(0, (pd.Timestamp(r["fecha_pago"]).date() - pd.Timestamp(r["fecha_vencimiento"]).date()).days), axis=1
            )
            df_tarde = df_pag2[df_pag2["_dias_tarde"] > 0].sort_values("_dias_tarde", ascending=False)

    total_pend_p = df[df["_ev"].isin(["PENDIENTE","SIN_FACTURA","VENCIDA"])]["monto_local"].sum()
    total_crit_p = df_crit_p["monto_local"].sum() if not df_crit_p.empty else 0
    avg_tarde = df_tarde["_dias_tarde"].mean() if not df_tarde.empty else 0

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    _kpi_card(c1, "Vencidas a pagar",   str(len(df_crit_p)), f"Q {total_crit_p:,.2f}",  C_DANGER)
    _kpi_card(c2, "Total pendiente",    f"Q {total_pend_p:,.2f}", f"{len(df_crit_p)+len(df_prev_p)} alertas", C_WARNING)
    _kpi_card(c3, "Por vencer pronto",  str(len(df_prev_p)), "próximos vencimientos",   theme_color)
    _kpi_card(c4, "Desvío promedio",    f"{avg_tarde:.0f} días", f"{len(df_tarde)} pagos tardíos", "#A855F7")

    st.markdown("")

    # Críticas
    if not df_crit_p.empty:
        st.markdown(f"<div style='color:{C_DANGER};font-weight:700;font-size:.78rem;letter-spacing:1px;text-transform:uppercase;margin:.5rem 0 .4rem;'>🚨 Pagos vencidos — Atención inmediata</div>", unsafe_allow_html=True)
        tc = st.session_state.get("tc", theme_color)
        for _, row in df_crit_p.iterrows():
            mora  = int(row["_alerta_dias"])
            monto = float(row.get("monto_local") or 0)
            fac   = _safe(row.get("numero_factura")) or "S/N"
            st.markdown(
                f"<div style='background:linear-gradient(135deg,{C_DANGER}15 0%,#1A1F2E 100%);"
                f"border-left:4px solid {C_DANGER};border-radius:8px;padding:.8rem 1.1rem;margin-bottom:.4rem;'>"
                "<div style='display:flex;justify-content:space-between;align-items:center;gap:1rem;'>"
                f"<div><div style='font-weight:700;color:#FAFAFA;'>{_safe(row.get('proveedor'))} · <span style='font-size:.82rem;color:#A0A4B8;'>{fac}</span></div>"
                f"<div style='font-size:.75rem;color:#A0A4B8;margin-top:3px;'>Venció hace <b>{mora} día{'s' if mora!=1 else ''}</b> · {_fmt_date(row.get('fecha_vencimiento'))}</div></div>"
                f"<div style='font-weight:800;color:{C_DANGER};white-space:nowrap;'>Q {monto:,.2f}</div>"
                "</div></div>", unsafe_allow_html=True
            )

    # Preventivas
    if not df_prev_p.empty:
        st.markdown(f"<div style='color:{C_WARNING};font-weight:700;font-size:.78rem;letter-spacing:1px;text-transform:uppercase;margin:1rem 0 .4rem;'>⚠️ Próximos vencimientos</div>", unsafe_allow_html=True)
        for _, row in df_prev_p.iterrows():
            dias_r = int(row["_alerta_dias"])
            monto  = float(row.get("monto_local") or 0)
            fac    = _safe(row.get("numero_factura")) or "S/N"
            label  = "vence hoy" if dias_r == 0 else f"vence en {dias_r}d"
            st.markdown(
                f"<div style='background:linear-gradient(135deg,{C_WARNING}12 0%,#1A1F2E 100%);"
                f"border-left:4px solid {C_WARNING};border-radius:8px;padding:.8rem 1.1rem;margin-bottom:.4rem;'>"
                "<div style='display:flex;justify-content:space-between;align-items:center;gap:1rem;'>"
                f"<div><div style='font-weight:700;color:#FAFAFA;'>{_safe(row.get('proveedor'))} · <span style='font-size:.82rem;color:#A0A4B8;'>{fac}</span></div>"
                f"<div style='font-size:.75rem;color:#A0A4B8;margin-top:3px;'><b>{label}</b> · {_fmt_date(row.get('fecha_vencimiento'))}</div></div>"
                f"<div style='font-weight:800;color:{C_WARNING};white-space:nowrap;'>Q {monto:,.2f}</div>"
                "</div></div>", unsafe_allow_html=True
            )

    # Desvíos
    if not df_tarde.empty:
        st.markdown("<div style='color:#A855F7;font-weight:700;font-size:.78rem;letter-spacing:1px;text-transform:uppercase;margin:1rem 0 .4rem;'>📊 Desvíos — Pagados fuera de término</div>", unsafe_allow_html=True)
        for _, row in df_tarde.iterrows():
            dias_t = int(row["_dias_tarde"])
            monto  = float(row.get("monto_local") or 0)
            st.markdown(
                "<div style='background:linear-gradient(135deg,#A855F715 0%,#1A1F2E 100%);"
                "border-left:4px solid #A855F7;border-radius:8px;padding:.7rem 1.1rem;margin-bottom:.4rem;'>"
                "<div style='display:flex;justify-content:space-between;align-items:center;gap:1rem;'>"
                f"<div><div style='font-weight:700;color:#FAFAFA;'>{_safe(row.get('proveedor'))}</div>"
                f"<div style='font-size:.75rem;color:#A0A4B8;'>Pagado <b>{dias_t} día{'s' if dias_t!=1 else ''}</b> tarde · Vto: {_fmt_date(row.get('fecha_vencimiento'))} → Pago: {_fmt_date(row.get('fecha_pago'))}</div></div>"
                f"<div style='font-weight:800;color:#A855F7;white-space:nowrap;'>Q {monto:,.2f}</div>"
                "</div></div>", unsafe_allow_html=True
            )

    if df_crit_p.empty and df_prev_p.empty:
        st.markdown(f"<div style='background:{C_SUCCESS}12;border:1px solid {C_SUCCESS}44;border-radius:10px;padding:1.5rem;text-align:center;'><div style='font-size:2rem;'>✅</div><div style='color:{C_SUCCESS};font-weight:700;'>Sin alertas de pago activas</div></div>", unsafe_allow_html=True)
        return

    # Email
    st.markdown("---")
    col_btn2, col_info2 = st.columns([1, 2])
    with col_btn2:
        if st.button("📧 Enviar informe de pagos", type="primary", use_container_width=True, key="btn_email_prov"):
            dests = [d.strip() for d in dest_text.strip().splitlines() if d.strip()]
            if not dests:
                st.error("Agregá al menos un destinatario en ⚙️ Configuración.")
            else:
                resumen_p = {"total_pend": total_pend_p, "n_criticas": len(df_crit_p), "n_prev": len(df_prev_p), "n_tarde": len(df_tarde)}
                html_p = _generar_html_email_proveedores(df_crit_p, df_prev_p, df_tarde, resumen_p)
                with st.spinner("Enviando..."):
                    ok, msg = _enviar_email(html_p, dests)
                if ok:
                    st.success(f"✅ Informe de pagos enviado a: {', '.join(dests)}")
                else:
                    st.error(f"❌ {msg}")
    with col_info2:
        dests_show = [d.strip() for d in dest_text.strip().splitlines() if d.strip()]
        st.caption("📧 " + " · ".join(dests_show) if dests_show else "Sin destinatarios")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main():
    pais_opciones = ["TODOS"] + PAISES

    col_flag, col_sel = st.columns([3, 1])
    with col_sel:
        pais_sel = st.selectbox(
            "🌎 País",
            pais_opciones,
            index=pais_opciones.index("GUATEMALA"),
            key="pais_filtro_global",
            label_visibility="collapsed",
        )

    theme  = COUNTRY_THEMES.get(pais_sel, COUNTRY_THEMES["TODOS"])
    color  = theme["primary"]
    color2 = theme["secondary"]
    flag   = theme["flag"]

    # Guardar en session_state para usarlos dentro de las tarjetas
    st.session_state["tc"]  = color
    st.session_state["tc2"] = color2

    st.markdown(f"""
    <style>
    /* Fondo general */
    .stApp {{
        background: linear-gradient(145deg, {color2}55 0%, #080D14 45%, #0E1117 100%) !important;
    }}
    /* Sidebar */
    section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {color2}77 0%, #080D14 100%) !important;
        border-right: 1px solid {color}33 !important;
    }}
    /* Scrollbar */
    ::-webkit-scrollbar-thumb {{ background: {color}99; border-radius: 4px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: {color} !important; }}
    /* Tabs */
    .stTabs [data-baseweb="tab-highlight"] {{ background-color: {color} !important; }}
    .stTabs [aria-selected="true"] {{ color: {color} !important; font-weight: 700 !important; }}
    .stTabs [data-baseweb="tab-list"] {{ border-bottom: 1px solid {color}33 !important; }}
    /* KPI metric cards */
    div[data-testid="metric-container"] {{
        background: linear-gradient(135deg, {color}20 0%, {color2}15 100%) !important;
        border: 1px solid {color}55 !important;
        box-shadow: 0 4px 20px {color}25 !important;
    }}
    /* Botones primarios */
    .stButton > button[kind="primary"] {{
        background: linear-gradient(90deg, {color} 0%, {color2} 100%) !important;
        border: none !important;
        color: white !important;
        font-weight: 700 !important;
    }}
    .stButton > button[kind="primary"]:hover {{
        opacity: 0.88 !important;
        transform: translateY(-1px);
    }}
    /* Inputs y selects */
    div[data-baseweb="select"] > div:first-child {{
        border-color: {color}66 !important;
        background: {color}0D !important;
    }}
    div[data-baseweb="input"] > div {{
        border-color: {color}44 !important;
        background: {color}0D !important;
    }}
    /* Divisor */
    hr {{ border-color: {color}33 !important; }}
    /* Radio tabs superiores */
    div[data-testid="stHorizontalBlock"] div[role="radiogroup"] label[data-selected="true"] {{
        color: {color} !important;
        border-bottom: 2px solid {color} !important;
    }}
    </style>
    """, unsafe_allow_html=True)

    with col_flag:
        st.markdown(
            f"<div style='background:linear-gradient(90deg,{color} 0%,{color2} 100%);"
            "border-radius:10px;padding:.5rem 1.4rem;"
            "display:flex;align-items:center;gap:.8rem;"
            f"box-shadow:0 4px 20px {color}55;'>"
            f"<span style='font-size:2rem;'>{flag}</span>"
            f"<span style='color:#fff;font-size:1.4rem;font-weight:800;letter-spacing:-.5px;'>Cuenta Corriente</span>"
            f"<span style='color:#ffffff99;font-size:.82rem;margin-left:auto;'>{theme['name']}</span>"
            "</div>",
            unsafe_allow_html=True
        )

    st.markdown(
        f"<p style='color:{color}99;font-size:.85rem;margin-top:.4rem;margin-bottom:1rem;'>"
        "Seguimiento de facturas de proveedores y clientes — pendientes, vencidas y pagadas/cobradas."
        "</p>",
        unsafe_allow_html=True
    )

    tab_prov, tab_cli, tab_alertas = st.tabs(["🏢 Proveedores", "👥 Clientes", "🔔 Alertas & Cobranza"])
    with tab_prov:
        _render_proveedores(pais_sel, color)
    with tab_cli:
        _render_clientes(pais_sel, color)
    with tab_alertas:
        _render_alertas(pais_sel, color)


if __name__ == "__main__":
    main()
