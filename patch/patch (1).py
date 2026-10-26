import re, sys, glob, os, zipfile

# stage 1: hook Application.onCreate in decoded smali
def hook(decoded):
    cands = glob.glob(os.path.join(decoded, "smali*", "com", "fongmi", "android", "tv", "App.smali"))
    if not cands:
        for f in glob.glob(os.path.join(decoded, "smali*", "**", "*.smali"), recursive=True):
            head = open(f, encoding="utf-8", errors="ignore").read(2000)
            if re.search(r"^\.super Landroid/app/Application;|^\.super Landroidx/multidex/MultiDexApplication;", head, re.M):
                cands.append(f)
    if not cands:
        sys.exit("Application smali not found")
    call = "    invoke-static {p0}, Lcom/patch/gate/PasswordGate;->install(Landroid/app/Application;)V\n"
    for f in cands:
        s = open(f, encoding="utf-8").read()
        m = re.search(r"\.method[^\n]* onCreate\(\)V\n(.*?)\.end method", s, re.S)
        if not m:
            continue
        body = m.group(1)
        sup = re.search(r"[ \t]*invoke-super \{p0\}, [^\n]*->onCreate\(\)V\n", body)
        if sup:
            pos = m.start(1) + sup.start()
        else:
            loc = re.search(r"[ \t]*\.(?:locals|registers) \d+\n", body)
            if not loc:
                continue
            pos = m.start(1) + loc.end()
        s = s[:pos] + call + s[pos:]
        open(f, "w", encoding="utf-8").write(s)
        print("hooked", f)
        return
    sys.exit("onCreate not found in " + str(cands))

# stage 2: put new dex files into a copy of the original apk (keeps resources untouched)
def repack(orig, rebuilt, gate_dex, out):
    zr = zipfile.ZipFile(rebuilt)
    new_dex = {n: zr.read(n) for n in zr.namelist() if re.fullmatch(r"classes\d*\.dex", n)}
    n = len(new_dex) + 1
    new_dex["classes%d.dex" % n] = open(gate_dex, "rb").read()
    zo = zipfile.ZipFile(orig)
    with zipfile.ZipFile(out, "w") as zw:
        for info in zo.infolist():
            name = info.filename
            if name.startswith("META-INF/") and re.search(r"\.(SF|RSA|DSA|EC)$|MANIFEST\.MF$", name):
                continue
            if name in new_dex:
                continue
            zw.writestr(info, zo.read(name), compress_type=info.compress_type)
        for name, data in new_dex.items():
            zw.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
    print("repacked ->", out, sorted(new_dex))

if sys.argv[1] == "hook":
    hook(sys.argv[2])
else:
    repack(*sys.argv[2:6])
