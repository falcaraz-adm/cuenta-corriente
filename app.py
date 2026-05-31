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


# ═════════════════════════════════════════════════════════════════════════════
# PROVEEDORES
# ═════════════════════════════════════════════════════════════════════════════

def _render_proveedores():
    hoy = datetime.date.today()
    df  = get_proveedores_cc()

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
    _kpi_card(c1, "Total Pendiente",  "Q " + f"{total_pend:,.2f}", str(len(df_pend))    + " facturas", "#FAFAFA")
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
            "<div style='background:#1A1F2E;border-left:4px solid " + border + ";"
            "border-radius:8px;padding:.8rem 1.1rem;margin-bottom:.5rem;'>"
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
        "¿Qué tenés disponible?",
        ["📄 Tengo la factura completa", "💰 Solo sé el monto (la factura llega después)"],
        horizontal=True, key="prov_modo_entrada"
    )
    tiene_factura = modo.startswith("📄")

    if not tiene_factura:
        st.info(
            "**Modo sin factura:** Registrás el monto y el proveedor. "
            "Cuando llegue la factura, editás este registro para agregar el N° y actualizás el estado."
        )

    with st.form("form_nueva_prov", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            proveedor = st.text_input("Proveedor *", placeholder="Ej. Impresos del Pacífico SA")
        with c2:
            pais = st.selectbox("País", PAISES, index=PAISES.index("GUATEMALA"))

        c3, c4 = st.columns(2)
        with c3:
            monto_gtq = st.number_input("Monto GTQ *", min_value=0.0, value=0.0, step=100.0, format="%.2f")
        with c4:
            monto_usd = st.number_input("Equivalente USD", min_value=0.0, value=0.0, step=10.0, format="%.2f")

        if tiene_factura:
            c5, c6 = st.columns(2)
            with c5:
                num_factura = st.text_input("N° Factura *", placeholder="FAC-2026-001")
            with c6:
                fecha_venc = st.date_input("Fecha de Vencimiento *", value=datetime.date.today() + datetime.timedelta(days=30))
        else:
            num_factura = ""
            fecha_venc  = st.date_input("Fecha estimada de vencimiento", value=datetime.date.today() + datetime.timedelta(days=30))

        obs = st.text_area("Observaciones / Referencia interna", placeholder="Ej. Orden de compra #456...", height=70)
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

def _render_clientes():
    hoy = datetime.date.today()
    df  = get_clientes_cc()

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
    _kpi_card(c1, "Por Cobrar",        "Q " + f"{total_pend:,.2f}", str(len(df_pend))    + " facturas", "#FAFAFA")
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
            "<div style='background:#1A1F2E;border-left:4px solid " + border + ";"
            "border-radius:8px;padding:.8rem 1.1rem;margin-bottom:.5rem;'>"
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

    with st.form("form_nueva_cli", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            cliente = st.text_input("Cliente *", placeholder="Ej. Ministerio de Salud GT")
        with c2:
            pais = st.selectbox("País", PAISES, index=PAISES.index("GUATEMALA"))

        c3, c4 = st.columns(2)
        with c3:
            num_factura = st.text_input("N° Factura *", placeholder="FAC-2026-001")
        with c4:
            monto_gtq = st.number_input("Monto GTQ *", min_value=0.0, value=0.0, step=100.0, format="%.2f")

        c5, c6, c7 = st.columns(3)
        with c5:
            monto_usd = st.number_input("Equivalente USD", min_value=0.0, value=0.0, step=10.0, format="%.2f")
        with c6:
            fecha_emision = st.date_input("Fecha de emisión *", value=datetime.date.today())
        with c7:
            fecha_venc = st.date_input("Fecha de vencimiento *", value=datetime.date.today() + datetime.timedelta(days=30))

        obs = st.text_area("Observaciones / Referencia", placeholder="Ej. Proyecto X, contrato 2026-12...", height=70)
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
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main():
    st.markdown("## 🏦 Cuenta Corriente")
    st.markdown(
        "<p style='color:#A0A4B8;font-size:.85rem;margin-top:-.5rem;margin-bottom:1rem;'>"
        "Seguimiento de facturas de proveedores y clientes — pendientes, vencidas y pagadas/cobradas."
        "</p>",
        unsafe_allow_html=True
    )

    tab_prov, tab_cli = st.tabs(["🏢 Proveedores", "👥 Clientes"])
    with tab_prov:
        _render_proveedores()
    with tab_cli:
        _render_clientes()


if __name__ == "__main__":
    main()
