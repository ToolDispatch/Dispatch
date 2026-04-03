import os, sys, tempfile, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scanner_dart import DartScanner

def _write(src):
    f = tempfile.NamedTemporaryFile(suffix=".dart", mode="w", delete=False, encoding="utf-8")
    f.write(src); f.close(); return f.name

def test_supports_dart():
    s = DartScanner()
    assert s.supports("foo.dart") and not s.supports("foo.ts") and not s.supports("foo.py")

def test_exports_class():
    st = DartScanner().scan(_write("class MyWidget extends StatelessWidget {}\n"))
    assert "MyWidget" in st.exports

def test_exports_function():
    st = DartScanner().scan(_write("void main() { }\n"))
    assert "main" in st.exports

def test_exports_future_function():
    st = DartScanner().scan(_write("Future<String> fetchData(String url) async { return ''; }\n"))
    assert "fetchData" in st.exports

def test_function_required_positional():
    st = DartScanner().scan(_write("String greet(String name, String greeting) { return greeting + name; }\n"))
    fn = st.functions.get("greet")
    assert fn and fn["n_required"] == 2 and fn["n_total"] == 2

def test_function_optional_positional():
    st = DartScanner().scan(_write("String greet(String name, [String greeting = 'Hello']) { return name; }\n"))
    fn = st.functions.get("greet")
    assert fn["n_required"] == 1 and fn["n_total"] == 2

def test_function_named_optional():
    st = DartScanner().scan(_write("String greet(String name, {String? greeting}) { return name; }\n"))
    fn = st.functions.get("greet")
    assert fn["n_required"] == 1 and fn["n_total"] == 2

def test_function_named_required():
    st = DartScanner().scan(_write("String greet({required String name, String? greeting}) { return name; }\n"))
    fn = st.functions.get("greet")
    assert fn["n_required"] == 1 and fn["n_total"] == 2

def test_stub_unimplemented():
    st = DartScanner().scan(_write("String todo(String a) { throw UnimplementedError(); }\n"))
    assert st.functions.get("todo", {}).get("is_stub")

def test_import_package():
    st = DartScanner().scan(_write("import 'package:flutter/material.dart';\n"))
    assert "package:flutter/material.dart" in st.imports

def test_import_show():
    st = DartScanner().scan(_write("import 'package:myapp/utils.dart' show fetchData, parseJson;\n"))
    names = [fi["name"] for fi in st.from_imports]
    assert "fetchData" in names and "parseJson" in names

def test_call_detection():
    st = DartScanner().scan(_write("void main() { greet('Alice', 'Hi'); }\n"))
    call = next((c for c in st.calls if c["symbol"] == "greet"), None)
    assert call and call["n_args"] == 2

def test_env_var_hard_dotenv():
    st = DartScanner().scan(_write("final key = dotenv.env['API_KEY'];\n"))
    assert any(e["var_name"] == "API_KEY" for e in st.env_vars_hard)

def test_env_var_soft_dotenv():
    st = DartScanner().scan(_write("final key = dotenv.env['API_KEY'] ?? 'default';\n"))
    assert any(e["var_name"] == "API_KEY" for e in st.env_vars_soft)

def test_env_var_hard_platform():
    st = DartScanner().scan(_write("final key = Platform.environment['SECRET'];\n"))
    assert any(e["var_name"] == "SECRET" for e in st.env_vars_hard)

def test_registry_scans_dart_file():
    from scanner_registry import scan_file
    st = scan_file(_write("String hello(String name) { return name; }\n"))
    assert st is not None and "hello" in st.exports
