#!/usr/bin/env python3
"""Generate ``src/logosc/types_test.logos`` from Python's own type spelling.

The parity half of the file is not transcribed by hand. Every row below names a
Logos source spelling and the ``logos.types`` value it stands for; the expected
text is whatever ``logos.check.mangle_type`` prints for that value, so the Logos
port is compared with the reference on the day the file is written. Rows the
reference cannot spell (``(ref …)``: ``mangle_type`` has no ``Ref`` branch) are
listed separately; the table records the reference's diagnostic and the port's
spelling.

The generated file is formatted with ``python3 -m logos fmt`` before this
script returns, so the output is a fixed point of the formatter.

    python3 tools/types_parity.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from logos.check import mangle_type  # noqa: E402
from logos.diag import LogosError  # noqa: E402
from logos.types import (  # noqa: E402
    Arr,
    Atomic,
    Chan,
    EnumRef,
    FnTy,
    Opt,
    Own,
    Prim,
    Ptr,
    Ref,
    Res,
    Shared,
    StructRef,
    Vec,
)

I = Prim("i64")
S = Prim("str")
VOID = Prim("void")
POINT = StructRef("point")
PARSE = EnumRef("parse-error")
E = StructRef("e")


def fn(params, ret, captures=False):
    return FnTy(tuple(params), ret, captures)


#: ``(name, logos source, table, value)``. ``table`` is ``""`` for none,
#: ``"struct"`` for a module that declares ``point``, ``"enum"`` for one that
#: declares ``parse-error``.
ROWS = [
    ("prim-i8", ":i8", "", Prim("i8")),
    ("prim-i16", ":i16", "", Prim("i16")),
    ("prim-i32", ":i32", "", Prim("i32")),
    ("prim-i64", ":i64", "", I),
    ("prim-u8", ":u8", "", Prim("u8")),
    ("prim-u16", ":u16", "", Prim("u16")),
    ("prim-u32", ":u32", "", Prim("u32")),
    ("prim-u64", ":u64", "", Prim("u64")),
    ("prim-f32", ":f32", "", Prim("f32")),
    ("prim-f64", ":f64", "", Prim("f64")),
    ("prim-bool", ":bool", "", Prim("bool")),
    ("prim-str", ":str", "", S),
    ("prim-void", ":void", "", VOID),
    ("prim-thread", ":thread", "", Prim("thread")),
    ("prim-mutex", ":mutex", "", Prim("mutex")),
    ("prim-run", ":run", "", Prim("run")),
    ("vec-str", "(vec :str)", "", Vec(S)),
    ("vec-vec-i64", "(vec (vec :i64))", "", Vec(Vec(I))),
    ("vec-ptr-u8", "(vec (ptr :u8))", "", Vec(Ptr(Prim("u8")))),
    ("vec-arr", "(vec (arr :i64 4))", "", Vec(Arr(I, 4))),
    ("ptr-point", "(ptr point)", "struct", Ptr(POINT)),
    ("ptr-vec", "(ptr (vec :i64))", "", Ptr(Vec(I))),
    ("ptr-ptr-point", "(ptr (ptr point))", "struct", Ptr(Ptr(POINT))),
    ("own-point", "(own point)", "struct", Own(POINT)),
    ("own-vec", "(own (vec :str))", "", Own(Vec(S))),
    ("arr-i64-4", "(arr :i64 4)", "", Arr(I, 4)),
    ("arr-vec-2", "(arr (vec :i64) 2)", "", Arr(Vec(I), 2)),
    ("arr-arr", "(arr (arr :i64 3) 2)", "", Arr(Arr(I, 3), 2)),
    ("arr-ptr-point", "(arr (ptr point) 8)", "struct", Arr(Ptr(POINT), 8)),
    ("arr-len-0", "(arr :bool 0)", "", Arr(Prim("bool"), 0)),
    ("opt-point", "(opt point)", "struct", Opt(POINT)),
    ("opt-vec", "(opt (vec :i64))", "", Opt(Vec(I))),
    ("opt-own-point", "(opt (own point))", "struct", Opt(Own(POINT))),
    ("res-i64-enum", "(res :i64 parse-error)", "enum", Res(I, PARSE)),
    ("res-vec-e", "(res (vec :i64) e)", "", Res(Vec(I), E)),
    ("res-i64-vec", "(res :i64 (vec :str))", "", Res(I, Vec(S))),
    ("res-opt-vec", "(res (opt :i64) (vec point))", "struct", Res(Opt(I), Vec(POINT))),
    ("shared-chan-point", "(shared (chan point))", "struct", Shared(Chan(POINT))),
    ("shared-atomic", "(shared (atomic :i64))", "", Shared(Atomic(I))),
    ("chan-str", "(chan :str)", "", Chan(S)),
    ("chan-vec-u8", "(chan (vec :u8))", "", Chan(Vec(Prim("u8")))),
    ("atomic-i64", "(atomic :i64)", "", Atomic(I)),
    ("atomic-bool", "(atomic :bool)", "", Atomic(Prim("bool"))),
    ("fn-two", "(fn :i64 ((a :i64) (b :str)))", "", fn([I, S], I)),
    ("fn-capture", "(fn* :void ((a point)))", "struct", fn([POINT], VOID, True)),
    ("fn-empty", "(fn :void ())", "", fn([], VOID)),
    ("fn-vec", "(fn (vec :i64) ((v (vec :i64))))", "", fn([Vec(I)], Vec(I))),
    (
        "fn-higher",
        "(fn (fn :i64 ((a :i64))) ((f (fn :i64 ((a :i64))))))",
        "",
        fn([fn([I], I)], fn([I], I)),
    ),
    ("fn-named-return", "(fn point ((a :i64)))", "struct", fn([I], POINT)),
    ("fn-named-return-two", "(fn point ((a :i64) (b point)))", "struct", fn([I, POINT], POINT)),
    ("struct-ref", "point", "struct", POINT),
    ("enum-ref", "parse-error", "enum", PARSE),
    ("struct-named-i64", "(ptr i64)", "", Ptr(StructRef("i64"))),
    ("vec-enum", "(vec parse-error)", "enum", Vec(PARSE)),
    ("res-enum-vec", "(res parse-error (vec parse-error))", "enum", Res(PARSE, Vec(PARSE))),
]

#: Rows the reference's ``mangle_type`` cannot spell: it has no ``Ref`` branch,
#: so a legal ``(ref (vec T))`` is E0101 "cannot mangle". The port spells it the
#: way the other unary wrappers spell theirs.
REF_ROWS = [
    ("ref-vec", "(ref (vec :i64))", "", Ref(Vec(I)), "ref(vec(i64))"),
    ("ref-vec-point", "(ref (vec point))", "struct", Ref(Vec(POINT)), "ref(vec(s5_point))"),
]

ARENA = [
    ("tags", ":i64"),
    ("names", ":str"),
    ("elem", ":i64"),
    ("extra", ":i64"),
    ("pbase", ":i64"),
    ("pnames", ":str"),
    ("ptypes", ":i64"),
    ("pattrs", ":i64"),
    ("pchild", ":i64"),
    ("powner", ":str"),
]

TREE = [("kinds", ":i64"), ("texts", ":str"), ("lines", ":i64"), ("cols", ":i64")]

ARGS = (
    " ".join(f"({v} (ref (vec {t})))" for v, t in ARENA)
    + " (kinds (ref (vec :i64))) (texts (ref (vec :str)))"
    + " (lines (ref (vec :i64))) (cols (ref (vec :i64)))"
    + " (nodes (ref (vec node))) (ntexts (ref (vec :str)))"
    + " (dnames (ref (vec :str))) (dids (ref (vec :i64)))"
    + " (slot (ref (vec :i64))) (out (ref (vec :str))) (vout (ref (vec :str)))"
    + " (bnames (ref (vec :str))) (btypes (ref (vec :i64)))"
)

CALL = (
    "tags names elem extra pbase pnames ptypes pattrs pchild powner "
    "kinds texts lines cols nodes ntexts dnames dids slot out vout bnames btypes"
)


def alloc() -> str:
    """The vectors one entry point owns, at a fresh scope."""
    out = []
    for vector, ty in ARENA + TREE:
        out.append(f"  (letmut {vector}\n    (vec {ty})\n    (make (vec {ty})))")
    out.append("  (letmut nodes\n    (vec node)\n    (make (vec node)))")
    for vector, ty in [
        ("ntexts", ":str"),
        ("dnames", ":str"),
        ("dids", ":i64"),
        ("slot", ":i64"),
        ("out", ":str"),
        ("vout", ":str"),
        ("bnames", ":str"),
        ("btypes", ":i64"),
    ]:
        out.append(f"  (letmut {vector}\n    (vec {ty})\n    (make (vec {ty})))")
    out.append("  (vec-push slot -1)")
    return "\n".join(out)


PRELUDE = (
    """(mod types-test)

(use lex)

(use tree)

(use types)

(fn t-free :void ("""
    + ARGS
    + """)
  (vec-free tags)
  (vec-free names)
  (vec-free elem)
  (vec-free extra)
  (vec-free pbase)
  (vec-free pnames)
  (vec-free ptypes)
  (vec-free pattrs)
  (vec-free pchild)
  (vec-free powner)
  (vec-free kinds)
  (vec-free texts)
  (vec-free lines)
  (vec-free cols)
  (vec-free nodes)
  (vec-free ntexts)
  (vec-free dnames)
  (vec-free dids)
  (vec-free slot)
  (vec-free out)
  (vec-free vout)
  (vec-free bnames)
  (vec-free btypes)
  (ret))

(fn t-diag :str ((e type-error))
  (ret (str-concat (type-code (get e code))
         (str-concat " " (get e message)))))

(fn t-join :str ((parts (ref (vec :str))))
  (letmut whole :str "")
  (letmut i :i64 0)
  (while (< i (vec-len parts))
    (set whole (str-concat whole
                 (str-concat (if (= i 0) "" ",") (vec-get parts i))))
    (set i (+ i 1)))
  (ret whole))

(fn t-tree type-error ("""
    + ARGS
    + """)
  (if (> (vec-len nodes) 0)
    (ret (type-pass))
    (type-nothing))
  (let t tree-error (tree-parse kinds texts lines cols nodes ntexts))
  (ret (if (tree-ok t)
         (type-pass)
         (type-fail 1 "" (str-concat "E0001 " (get t msg))))))

(fn t-form :i64 ((nodes (ref (vec node))) (k :i64))
  (letmut f :i64 (get (vec-get nodes 0) first))
  (letmut i :i64 1)
  (while (and (< i k) (not (= f -1)))
    (set f (get (vec-get nodes f) next))
    (set i (+ i 1)))
  (ret f))

(fn t-item :i64 ((nodes (ref (vec node))) (ntexts (ref (vec :str))) (k :i64))
  (let form :i64 (t-form nodes k))
  (let c2 :i64 (type-nth nodes form 1))
  (ret (if (and (= (get (vec-get nodes c2) tok) 2)
             (str-eq (type-text nodes ntexts c2) ":"))
         (type-nth nodes form 2)
         c2)))

(fn t-parse type-error ("""
    + ARGS
    + """ (k :i64))
  (letmut e type-error (t-tree """
    + CALL
    + """))
  (if (not (type-ok e))
    (ret e)
    (type-nothing))
  (ret (type-parse nodes ntexts dnames dids tags names elem extra pbase powner
         pnames ptypes (t-item nodes ntexts k) "" slot)))

(fn t-push-row :void ((dnames (ref (vec :str))) (dids (ref (vec :i64))) (name :str) (id :i64))
  (vec-push dnames name)
  (vec-push dids id)
  (ret))

(fn t-declare :void ("""
    + ARGS
    + """ (table :str))
  (if (str-eq table "struct")
    (t-push-row dnames dids "point" (t-struct """
    + CALL
    + """ "m"))
    (type-nothing))
  (if (str-eq table "enum")
    (t-push-row dnames dids "parse-error" (t-enum """
    + CALL
    + """ "parse-error" "m"))
    (type-nothing))
  (ret))

(fn t-struct :i64 ("""
    + ARGS
    + """ (owner :str))
  (let start :i64 (type-field-start pchild))
  (vec-push ntexts "x")
  (type-field pattrs pchild (- (vec-len ntexts) 1)
    (type-prim tags names elem extra pbase powner "i64"))
  (vec-push ntexts "y")
  (type-field pattrs pchild (- (vec-len ntexts) 1)
    (type-prim tags names elem extra pbase powner "i64"))
  (ret (type-struct tags names elem extra pbase powner "point" owner start 2)))

(fn t-enum :i64 ("""
    + ARGS
    + """ (name :str) (owner :str))
  (let start :i64 (type-field-start pchild))
  (vec-push ntexts "ok")
  (type-field pattrs pchild (- (vec-len ntexts) 1)
    (type-prim tags names elem extra pbase powner "i64"))
  (vec-push ntexts "bad")
  (type-field pattrs pchild (- (vec-len ntexts) 1) -1)
  (ret (type-enum tags names elem extra pbase powner name owner start 2)))

(fn t-spell-of :str ("""
    + ARGS
    + """)
  (letmut m type-error (type-mangle tags names elem extra pbase ptypes
                         (vec-get slot 0) "" out))
  (ret (if (type-ok m)
         (vec-get out 0)
         (t-diag m))))
"""
)

BODY = (
    """(fn t-body-spell :str ("""
    + ARGS
    + """ (a :str) (b :str))
  (letmut e type-error (t-parse """
    + CALL
    + """ 1))
  (ret (if (not (type-ok e))
         (t-diag e)
         (t-spell-of """
    + CALL
    + """))))

(fn t-body-table :str ("""
    + ARGS
    + """ (table :str) (table2 :str))
  (t-declare """
    + CALL
    + """ table)
  (ret (t-body-spell """
    + CALL
    + """ table table2)))

(fn t-body-compat :str ("""
    + ARGS
    + """ (a :str) (b :str))
  (letmut e type-error (t-parse """
    + CALL
    + """ 1))
  (if (not (type-ok e))
    (ret (t-diag e))
    (type-nothing))
  (let left :i64 (vec-get slot 0))
  (vec-set slot 0 -1)
  (set e (t-parse """
    + CALL
    + """ 2))
  (if (not (type-ok e))
    (ret (t-diag e))
    (type-nothing))
  (ret (if (type-compatible tags names powner elem extra pbase ptypes
             left (vec-get slot 0))
         "true" "false")))

(fn t-body-subst :str ("""
    + ARGS
    + """ (a :str) (b :str))
  (letmut e type-error (t-parse """
    + CALL
    + """ 1))
  (if (not (type-ok e))
    (ret (t-diag e))
    (type-nothing))
  (let ty :i64 (vec-get slot 0))
  (vec-set slot 0 -1)
  (set e (t-parse """
    + CALL
    + """ 2))
  (if (not (type-ok e))
    (ret (t-diag e))
    (type-nothing))
  (vec-push bnames a)
  (vec-push btypes (vec-get slot 0))
  (vec-set slot 0 (type-substitute tags names elem extra pbase powner pnames ptypes
                    bnames btypes ty))
  (ret (t-spell-of """
    + CALL
    + """)))

(fn t-body-vars :str ("""
    + ARGS
    + """ (a :str) (b :str))
  (letmut e type-error (t-parse """
    + CALL
    + """ 1))
  (if (not (type-ok e))
    (ret (t-diag e))
    (type-nothing))
  (type-variables tags names elem extra pbase ptypes (vec-get slot 0) vout)
  (ret (t-join vout)))

(fn t-body-has :str ("""
    + ARGS
    + """ (a :str) (b :str))
  (letmut e type-error (t-parse """
    + CALL
    + """ 1))
  (ret (if (not (type-ok e))
         (t-diag e)
         (if (type-has-var tags names elem extra pbase ptypes (vec-get slot 0))
           "true" "false"))))

(fn t-body-mangle-error :str ("""
    + ARGS
    + """ (a :str) (b :str))
  (letmut e type-error (t-parse """
    + CALL
    + """ 1))
  (ret (if (not (type-ok e))
         (t-diag e)
         (t-spell-of """
    + CALL
    + """))))

(fn t-body-parse-error :str ("""
    + ARGS
    + """ (a :str) (b :str))
  (letmut e type-error (t-parse """
    + CALL
    + """ 1))
  (ret (if (type-ok e) "OK" (t-diag e))))

(fn t-body-decl :str ("""
    + ARGS
    + """ (a :str) (b :str))
  (let id :i64 (t-struct """
    + CALL
    + """ "m"))
  (ret (str-concat (type-decl-spelling names powner id false)
         (str-concat " " (type-decl-spelling names powner id true)))))

(fn t-body-fields :str ("""
    + ARGS
    + """ (a :str) (b :str))
  (let id :i64 (t-struct """
    + CALL
    + """ "m"))
  (ret (str-concat (str-from-i64 (type-field-count extra id))
         (str-concat " "
           (str-concat (type-field-name ntexts pattrs pbase id 0)
             (str-concat " "
               (str-concat (type-field-name ntexts pattrs pbase id 1)
                 (str-concat " "
                   (type-spell tags names elem extra pbase ptypes
                     (type-field-type pchild pbase id 0))))))))))

(fn t-body-variant :str ("""
    + ARGS
    + """ (a :str) (b :str))
  (let id :i64 (t-enum """
    + CALL
    + """ "parse-error" "m"))
  (ret (str-concat (str-from-i64 (type-field-count extra id))
         (str-concat " "
           (str-concat (type-field-name ntexts pattrs pbase id 1)
             (str-concat " "
               (str-from-i64 (type-field-type pchild pbase id 1))))))))

(fn t-body-owner :str ("""
    + ARGS
    + """ (a :str) (b :str))
  (let left :i64 (t-struct """
    + CALL
    + """ "left"))
  (let right :i64 (t-struct """
    + CALL
    + """ "right"))
  (ret (str-concat (if (type-compatible tags names powner elem extra pbase ptypes left right)
                       "true" "false")
         (str-concat " "
           (str-concat (type-spell tags names elem extra pbase ptypes left)
             (str-concat " "
               (str-concat (type-spell tags names elem extra pbase ptypes right)
                 (str-concat " "
                   (if (type-compatible tags names powner elem extra pbase ptypes
                          left left)
                     "true" "false")))))))))
"""
)

ENTRIES = [
    ("t-spell", "", ' "" ""', "t-body-spell"),
    ("t-spell-table", " (mode :str)", ' mode ""', "t-body-table"),
    ("t-compat", "", ' "" ""', "t-body-compat"),
    ("t-subst", " (var :str)", ' var ""', "t-body-subst"),
    ("t-vars", "", ' "" ""', "t-body-vars"),
    ("t-has", "", ' "" ""', "t-body-has"),
    ("t-mangle-error", "", ' "" ""', "t-body-mangle-error"),
    ("t-parse-error", "", ' "" ""', "t-body-parse-error"),
    ("t-decl", "", ' "" ""', "t-body-decl"),
    ("t-fields", "", ' "" ""', "t-body-fields"),
    ("t-variant", "", ' "" ""', "t-body-variant"),
    ("t-owner", "", ' "" ""', "t-body-owner"),
]


def wrapper(name: str, extra_params: str, extra_args: str, body: str) -> str:
    """One ``t-*`` entry point: allocate, lex once, run ``body``, free."""
    params = "(src :str)" + extra_params
    return (
        f"(fn {name} :void ({params})\n"
        f"{alloc()}\n"
        '  (letmut line :str "")\n'
        "  (let lexed lex-error (lex src kinds texts lines cols))\n"
        "  (if (lex-ok lexed)\n"
        f"    (set line ({body} {CALL}{extra_args}))\n"
        '    (set line (str-concat "E0006 " (get lexed msg))))\n'
        f"  (t-free {CALL})\n"
        "  (println line))"
    )


def source(*types: str) -> str:
    """A program whose k-th top-level form annotates ``a``, ``b``, …"""
    forms = []
    for name, ty in zip("abcdef", types):
        marker = ":" if ty.startswith("(") else ""
        forms.append(f"(let {name} {marker}{ty} 0)")
    return "".join(forms)


def escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def test(name: str, call: str, expected: str) -> str:
    return (
        f"(test {name}\n"
        f'  (expect (out "{escape(expected)}\\n")\n'
        "    (code 0)\n"
        "    (leaks 0))\n"
        f"  {call})"
    )


SUITE = """
(test compat-vec-same
  (expect (out "true\\n")
    (code 0)
    (leaks 0))
  (t-compat "%(vec_same)s"))

(test compat-width
  (expect (out "false\\n")
    (code 0)
    (leaks 0))
  (t-compat "%(width)s"))

(test compat-arr-length
  (expect (out "false\\n")
    (code 0)
    (leaks 0))
  (t-compat "%(arr_len)s"))

(test compat-fn-captures
  (expect (out "false\\n")
    (code 0)
    (leaks 0))
  (t-compat "%(fn_captures)s"))

(test compat-fn-param-names
  (expect (out "true\\n")
    (code 0)
    (leaks 0))
  (t-compat "%(fn_names)s"))

(test compat-var-same
  (expect (out "true\\n")
    (code 0)
    (leaks 0))
  (t-compat "%(var_same)s"))

(test compat-var-different
  (expect (out "false\\n")
    (code 0)
    (leaks 0))
  (t-compat "%(var_diff)s"))

(test compat-var-is-not-a-wildcard
  (expect (out "false\\n")
    (code 0)
    (leaks 0))
  (t-compat "%(var_prim)s"))

(test compat-owner
  (expect (out "false s5_point s5_point true\\n")
    (code 0)
    (leaks 0))
  (t-owner ""))

(test subst-vector
  (expect (out "vec(vec(i64))\\n")
    (code 0)
    (leaks 0))
  (t-subst "%(subst_vec)s" "T"))

(test subst-fn
  (expect (out "fn(vec(str))str\\n")
    (code 0)
    (leaks 0))
  (t-subst "%(subst_fn)s" "T"))

(test subst-leaves-unbound
  (expect (out "E0501 type variable U cannot be a type argument\\n")
    (code 0)
    (leaks 0))
  (t-subst "%(subst_unbound)s" "T"))

(test vars-params-before-return
  (expect (out "U,V,T\\n")
    (code 0)
    (leaks 0))
  (t-vars "%(vars_fn)s"))

(test vars-nested
  (expect (out "T,U\\n")
    (code 0)
    (leaks 0))
  (t-vars "%(vars_res)s"))

(test has-var-yes
  (expect (out "true\\n")
    (code 0)
    (leaks 0))
  (t-has "%(has_yes)s"))

(test has-var-no
  (expect (out "false\\n")
    (code 0)
    (leaks 0))
  (t-has "%(has_no)s"))

(test mangle-var-error
  (expect (out "E0501 type variable T cannot be a type argument\\n")
    (code 0)
    (leaks 0))
  (t-mangle-error "%(mangle_var)s"))

(test parse-unknown-primitive
  (expect (out "E0101 unknown type ':nope'\\n")
    (code 0)
    (leaks 0))
  (t-parse-error "%(bad_prim)s"))

(test parse-unknown-form
  (expect (out "E0101 unknown type form 'wat'\\n")
    (code 0)
    (leaks 0))
  (t-parse-error "%(bad_form)s"))

(test parse-ref-non-vector
  (expect (out "E0100 a ref may name a vector only\\n")
    (code 0)
    (leaks 0))
  (t-parse-error "%(bad_ref)s"))

(test parse-arr-length-name
  (expect (out "E0101 an array length must be a non-negative integer\\n")
    (code 0)
    (leaks 0))
  (t-parse-error "%(bad_len)s"))

(test parse-arr-length-negative
  (expect (out "E0101 an array length must be a non-negative integer\\n")
    (code 0)
    (leaks 0))
  (t-parse-error "%(bad_len2)s"))

(test parse-empty-list
  (expect (out "E0101 expected a type, found an empty list\\n")
    (code 0)
    (leaks 0))
  (t-parse-error "%(bad_empty)s"))

(test parse-arity
  (expect (out "E0101 vec takes one element type\\n")
    (code 0)
    (leaks 0))
  (t-parse-error "%(bad_arity)s"))

(test parse-number
  (expect (out "E0101 expected a type, found number\\n")
    (code 0)
    (leaks 0))
  (t-parse-error "%(bad_number)s"))

(test parse-string
  (expect (out "E0101 expected a type, found string\\n")
    (code 0)
    (leaks 0))
  (t-parse-error "%(bad_string)s"))

(test parse-param-needs-a-type
  (expect (out "E0002 a parameter must be (name type)\\n")
    (code 0)
    (leaks 0))
  (t-parse-error "%(bad_param)s"))

(test decl-spelling
  (expect (out "point m.point\\n")
    (code 0)
    (leaks 0))
  (t-decl ""))

(test struct-fields
  (expect (out "2 x y i64\\n")
    (code 0)
    (leaks 0))
  (t-fields ""))

(test enum-payloadless-variant
  (expect (out "2 bad -1\\n")
    (code 0)
    (leaks 0))
  (t-variant ""))
""" % {
    "vec_same": source("(vec :i64)", "(vec :i64)"),
    "width": source("(vec :i64)", "(vec :i32)"),
    "arr_len": source("(arr :i64 4)", "(arr :i64 5)"),
    "fn_captures": source("(fn :i64 ((a :i64)))", "(fn* :i64 ((a :i64)))"),
    "fn_names": source("(fn :i64 ((a :i64)))", "(fn :i64 ((b :i64)))"),
    "var_same": source("T", "T"),
    "var_diff": source("T", "U"),
    "var_prim": source("T", ":i64"),
    "subst_vec": source("(vec T)", "(vec :i64)"),
    "subst_fn": source("(fn T ((a (vec T))))", ":str"),
    "subst_unbound": source("(vec U)", ":i64"),
    "vars_fn": source("(fn :T ((a (vec U)) (b :V)))"),
    "vars_res": source("(res T (vec U))"),
    "has_yes": source("(res T :i64)"),
    "has_no": source("(res :i64 (vec :str))"),
    "mangle_var": source("(vec T)"),
    "bad_prim": source(":nope"),
    "bad_form": source("(wat :i64)"),
    "bad_ref": source("(ref :i64)"),
    "bad_len": source("(arr :i64 x)"),
    "bad_len2": source("(arr :i64 -1)"),
    "bad_empty": source("()"),
    "bad_arity": source("(vec)"),
    "bad_number": source("42"),
    "bad_string": '(let a \\"s\\" 0)',
    "bad_param": source("(fn :i64 ((a :i64) (b)))"),
}


def _ref_note(ty) -> str:
    try:
        mangle_type(ty)
    except LogosError as error:
        return f"{error.code} {error.message}"
    raise SystemExit("expected the reference to refuse a ref")


def build() -> tuple[str, list[tuple[str, ...]]]:
    parts = [PRELUDE, BODY]
    for name, extra, args, body in ENTRIES:
        parts.append(wrapper(name, extra, args, body))

    table: list[tuple[str, ...]] = []
    for index, (name, src, table_mode, ty) in enumerate(ROWS, start=1):
        spelling = mangle_type(ty)
        table.append((src, table_mode or "-", spelling, "same"))
        fn = "t-spell" if table_mode == "" else "t-spell-table"
        args = f'"{source(src)}"' + ("" if table_mode == "" else f' "{table_mode}"')
        parts.append(test(f"parity-{index:02d}-{name}", f"({fn} {args})", spelling))
    for index, (name, src, table_mode, ty, spelling) in enumerate(REF_ROWS, start=1):
        table.append((src, table_mode or "-", spelling, _ref_note(ty)))
        fn = "t-spell" if table_mode == "" else "t-spell-table"
        args = f'"{source(src)}"' + ("" if table_mode == "" else f' "{table_mode}"')
        parts.append(test(f"ref-{index:02d}-{name}", f"({fn} {args})", spelling))

    parts.append(SUITE.strip())
    return "\n\n".join(parts) + "\n", table


def main() -> int:
    text, table = build()
    path = ROOT / "src/logosc/types_test.logos"
    path.write_text(text, encoding="utf-8")
    subprocess.run(
        [sys.executable, "-m", "logos", "fmt", str(path)],
        cwd=ROOT,
        check=True,
    )
    print(f"{path.relative_to(ROOT)}: {len(ROWS) + len(REF_ROWS)} parity rows")
    for row in table:
        print(" | ".join(row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
