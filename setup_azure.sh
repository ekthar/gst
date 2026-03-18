#!/bin/bash
# GST HSN Resolver - Setup & Run Guide for Azure Linux

echo "=================================================="
echo "GST HSN Resolver - Setup for Azure Linux"
echo "=================================================="

# Check if already in gst directory
if [ ! -f "requirements.txt" ]; then
    echo "❌ Error: Must run from ~/gst directory"
    echo "Usage:"
    echo "  cd ~/gst"
    echo "  chmod +x setup_azure.sh"
    echo "  ./setup_azure.sh"
    exit 1
fi

echo ""
echo "Step 1: Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
echo "✅ Virtual environment created"

echo ""
echo "Step 2: Upgrading pip..."
pip install --upgrade pip
echo "✅ Pip upgraded"

echo ""
echo "Step 3: Installing dependencies..."
pip install -r requirements.txt
echo "✅ Dependencies installed"

echo ""
echo "Step 4: Verifying installation..."
python -c "from gst_hsn_tool import db; print('✅ Core modules working')" || {
    echo "❌ Import test failed"
    echo "Fix: Add src directory to PYTHONPATH"
    export PYTHONPATH="${PWD}/src:${PYTHONPATH}"
    echo "PYTHONPATH set to: $PYTHONPATH"
}

echo ""
echo "=================================================="
echo "✅ Setup Complete!"
echo "=================================================="

echo ""
echo "To run the web app:"
echo ""
echo "1. Interactive mode (see logs):"
echo "   python run_web_app.py --server.address 0.0.0.0 --server.port 8501"
echo ""
echo "2. Background mode (daemon):"
echo "   nohup python run_web_app.py --server.address 0.0.0.0 --server.port 8501 > web.log 2>&1 &"
echo "   tail -f web.log"
echo ""
echo "3. Or use the standard streamlit command:"
echo "   export PYTHONPATH=\"${PWD}/src:\${PYTHONPATH}\""
echo "   python -m streamlit run src/gst_hsn_tool/web_app.py --server.address 0.0.0.0 --server.port 8501"
echo ""
echo "Then open browser:"
echo "   http://$(hostname -I | awk '{print $1}'):8501"
echo ""
echo "=================================================="
