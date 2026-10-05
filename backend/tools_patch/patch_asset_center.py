# -*- coding: utf-8 -*-
import io, ast
p = r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\frontend\app\assets\center\page.tsx"
s = io.open(p, encoding="utf-8").read()
old = """        </div>
      )}
    </DashboardShell>
  );
}"""
new = """        </div>
      )}
      </div>
    </DashboardShell>
  );
}"""
assert old in s, "anchor missing"
s = s.replace(old, new, 1)
io.open(p, "w", encoding="utf-8").write(s)
print("PATCH OK")
