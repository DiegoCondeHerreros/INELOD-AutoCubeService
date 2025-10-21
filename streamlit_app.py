# streamlit_app.py
import re
from pathlib import Path
import optimized_script
import streamlit as st

st.set_page_config(page_title="GenAutoCubesRDF", page_icon="📊")
st.title("Generación Automática de Cubos RDF del Instituto Nacional de Estadística (INE)")
st.write("Sube un archivo CSV, especifica la medida y descarga RDF (Turtle).")

# --- Inputs ---
uploaded = st.file_uploader("Fichero CSV", type=["csv"])
measures = st.text_input("Columna de medida", value="value")

# Where we save files locally (ephemeral in hosted environments like HF Spaces)
UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)

def _safe_name(name: str) -> str:
    """Make a safe filename: keep letters, numbers, dot, dash, underscore."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)

def _save_uploaded_file(uploaded_file) -> Path:
    """Persist the uploaded CSV to disk using its original name."""
    original = uploaded_file.name or "data.csv"
    safe = _safe_name(original)
    target = UPLOADS_DIR / safe
    # Write file bytes
    target.write_bytes(uploaded_file.getvalue())
    return target

def _safe_unlink(p: Path):
    try:
        p.unlink(missing_ok=True)   # Python 3.8+; ignores if not present
    except Exception:
        pass

def _save_uploaded_file_streaming(uploaded_file, target: Path, show_progress: bool = True) -> Path:
    """
    Save the uploaded file to disk WITHOUT loading it fully in memory.
    Writes in 1MB chunks and optionally shows a progress bar.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    total = getattr(uploaded_file, "size", None)  # may be None locally; present on Spaces
    chunk_size = 1024 * 1024  # 1 MB

    progress = st.progress(0) if (show_progress and total) else None
    written = 0

    with target.open("wb") as f:
        while True:
            chunk = uploaded_file.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            if progress and total:
                written += len(chunk)
                progress.progress(min(written / total, 1.0))

    # Reset pointer if you need to read the Streamlit buffer again
    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    if progress:
        progress.empty()

    return target


# --- Action ---
if st.button("Convert"):
    if not uploaded:
        st.warning("Please upload a CSV file.")
    elif not measures.strip():
        st.warning("Please provide measure column.")
    else:
        try:
            # 1) Save the uploaded file to disk (same name)
            #saved_path = _save_uploaded_file(uploaded)
            safe_name = _safe_name(uploaded.name )
            saved_path = _save_uploaded_file_streaming(uploaded, UPLOADS_DIR / safe_name)
            st.info(f"Saved file to: `{saved_path}`")

            # 2) Call your function with the *path*
            optimized_script.run(
                str(saved_path),
                measures
            )
            # 3) Output
            st.success("Conversion successful!")
            # prepare download of produced file (knowledgegraph.nt)
            candidates = [
                saved_path.parent / "knowledge-graph.nt",
                Path("knowledge-graph.nt"),
                UPLOADS_DIR / "knowledge-graph.nt",
            ]
            kg_path = next((p for p in candidates if p.exists()), None)

            if kg_path:
                kg_bytes = kg_path.read_bytes()
                st.download_button(
                    "Download RDF (Turtle)",
                    kg_bytes,
                    file_name="knowledge-graph.nt",
                    mime="text/turtle",
                )
            else:
                st.warning("Could not find 'knowledgegraph.nt' for download.")

        except Exception as e:
            st.error(f"Error: {e}")
        
        finally:
            # 5) Always delete the uploaded file after processing (success or error)
            if saved_path is not None:
                _safe_unlink(saved_path)
