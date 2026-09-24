import streamlit as st

def render_footer():
    """Renders a fixed footer at the bottom of the viewport across all pages."""
    st.markdown(
        """
        <style>
        /* Ensure content doesn't get covered by the fixed footer */
        .stApp .block-container {
            padding-bottom: 4.5rem !important;
        }

        .fixed-footer-container {
            position: fixed;
            left: 0;
            bottom: 0;
            width: 100%;
            padding: 7px 16px;
            text-align: center;
            font-size: 0.78rem;
            line-height: 1.35;
            background: rgba(255, 255, 255, 0.94);
            color: #555555;
            border-top: 1px solid rgba(0, 0, 0, 0.08);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            z-index: 99;
            box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.04);
            pointer-events: auto;
        }

        @media (prefers-color-scheme: dark) {
            .fixed-footer-container {
                background: rgba(14, 17, 23, 0.94);
                color: #b0b0b0;
                border-top: 1px solid rgba(255, 255, 255, 0.12);
                box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.3);
            }
        }
        </style>
        <div class="fixed-footer-container">
            © <strong>Vince Coppens</strong> — Sole Intellectual Property. All rights reserved. • Access &amp; use by approval only • Provided "as-is" without guarantees on personal infrastructure.
        </div>
        """,
        unsafe_allow_html=True
    )
