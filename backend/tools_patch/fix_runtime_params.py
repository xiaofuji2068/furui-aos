# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\frontend\app\pages\[code]\page.tsx")
t = p.read_text(encoding="utf-8")
t2 = t.replace('import { use, useEffect, useState } from "react";', 'import { useEffect, useState } from "react";')
t2 = t2.replace('export default function PageRuntime({ params }: { params: Promise<{ code: string }> }) {\n  const { code } = use(params);',
                'export default function PageRuntime({ params }: { params: { code: string } }) {\n  const { code } = params;')
assert t2 != t
p.write_text(t2, encoding="utf-8")
print("runtime params -> sync Next14 style")