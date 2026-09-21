"""
Design pattern detector for Python code.

Identifies common design patterns from class structure, inheritance,
method signatures, and call relationships. Each detection returns
evidence with line numbers so findings are auditable.

Supported patterns (structural detection, conservative scoring):
- Repository:    data access abstraction with CRUD operations
- Service:       stateless business logic facade / orchestration
- Factory:       object creation delegation (Factory Method / Abstract Factory)
- Singleton:     single instance enforcement
- Strategy:      interchangeable algorithms via common interface
- Observer:      event notification / pub-sub
- State:         behavior changes based on internal state / FSM
- Template Method: skeleton algorithm with subclass steps
- Adapter:       interface conversion / wrapping
- Composite:     tree structure of uniform objects

Detection is conservative: we require structural evidence and return
a confidence score, not a binary yes/no.
"""

from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple


@dataclass
class PatternEvidence:
    """A single piece of evidence for a pattern match."""
    description: str
    filepath: str = ""
    line_start: int = 0
    line_end: int = 0
    evidence_type: str = "structure"  # structure | naming | method | inheritance


@dataclass
class DetectedPattern:
    """A detected design pattern in the project."""
    pattern_id: str
    pattern_name: str        # English name (UI can map to i18n)
    category: str            # creational | structural | behavioral
    confidence: str          # high | medium | low
    score: float             # 0.0 - 1.0
    target_type: str         # class | module | project
    target_name: str
    filepath: str = ""
    description: str = ""
    evidence: List[PatternEvidence] = field(default_factory=list)
    related_classes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "category": self.category,
            "confidence": self.confidence,
            "score": round(self.score, 2),
            "target_type": self.target_type,
            "target_name": self.target_name,
            "filepath": self.filepath,
            "description": self.description,
            "evidence": [
                {
                    "description": e.description,
                    "filepath": e.filepath,
                    "line_start": e.line_start,
                    "line_end": e.line_end,
                    "evidence_type": e.evidence_type,
                }
                for e in self.evidence
            ],
            "related_classes": self.related_classes,
        }


@dataclass
class ClassInfo:
    """Lightweight class info for pattern detection."""
    name: str
    module_name: str
    filepath: str
    bases: List[str]
    methods: Dict[str, ast.FunctionDef] = field(default_factory=dict)
    method_names: List[str] = field(default_factory=list)
    class_attributes: Set[str] = field(default_factory=set)
    instance_attributes: Set[str] = field(default_factory=set)  # from __init__
    start_line: int = 0
    end_line: int = 0
    docstring: str = ""


@dataclass
class DesignPatternResult:
    patterns: List[DetectedPattern] = field(default_factory=list)

    @property
    def by_category(self) -> Dict[str, List[DetectedPattern]]:
        cats: Dict[str, List[DetectedPattern]] = {}
        for p in self.patterns:
            cats.setdefault(p.category, []).append(p)
        return cats

    @property
    def sorted_by_score(self) -> List[DetectedPattern]:
        return sorted(self.patterns, key=lambda p: p.score, reverse=True)

    def to_dict(self) -> dict:
        return {
            "patterns": [p.to_dict() for p in self.sorted_by_score],
            "total": len(self.patterns),
            "by_category": {
                cat: [p.to_dict() for p in plist]
                for cat, plist in self.by_category.items()
            },
        }


class DesignPatternDetector:
    """
    Detect design patterns from parsed Python source.

    Works from a list of ClassInfo objects collected across the project.
    Each detector is a method that checks a specific pattern and returns
    zero or more DetectedPattern instances.

    All detection strings use English to avoid encoding issues; frontends
    can map pattern_id to localized display names.
    """

    def __init__(self):
        self.classes: List[ClassInfo] = []
        self._class_by_name: Dict[str, ClassInfo] = {}

    # ---- Public API ----

    def detect_from_project(self, project_info) -> DesignPatternResult:
        """Run detection against a parsed project."""
        self._collect_classes(project_info)
        return self.detect()

    def detect_from_files(self, files: List[Tuple[str, str, str]]) -> DesignPatternResult:
        """Run detection from raw files: list of (module_name, filepath, source)."""
        self.classes = []
        for module_name, filepath, source in files:
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef):
                    self.classes.append(self._build_class_info(node, module_name, filepath))
        self._build_index()
        return self.detect()

    def detect(self) -> DesignPatternResult:
        """Run all detectors and collect results."""
        result = DesignPatternResult()

        detectors = [
            self._detect_repository,
            self._detect_service,
            self._detect_factory,
            self._detect_state,
            self._detect_singleton,
            self._detect_strategy,
            self._detect_observer,
            self._detect_template_method,
            self._detect_adapter,
            self._detect_composite,
        ]

        for detector in detectors:
            try:
                found = detector()
                result.patterns.extend(found)
            except Exception:
                continue

        return result

    # ---- Class collection ----

    def _collect_classes(self, project_info):
        """Collect classes from a ProjectInfo object.

        Reads source from file paths and parses AST so we get full
        method bodies, attribute assignments, etc.
        """
        self.classes = []

        files = getattr(project_info, 'files', []) or []
        for f in files:
            module_name = getattr(f, 'module_name', '')
            filepath = getattr(f, 'filepath', '')
            parsed = getattr(f, 'parsed', None)
            if not parsed or not filepath:
                continue

            # Read source from file (most reliable for AST analysis)
            source = ''
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as sf:
                        source = sf.read()
                except (IOError, UnicodeDecodeError):
                    pass

            if not source:
                # Fallback: join source_lines
                sl = getattr(parsed, 'source_lines', []) or []
                source = '\n'.join(sl) if sl else ''

            if not source:
                continue

            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef):
                    ci = self._build_class_info(node, module_name, filepath)
                    self.classes.append(ci)

        self._build_index()

    def _build_class_info(self, node: ast.ClassDef, module_name: str, filepath: str) -> ClassInfo:
        """Build ClassInfo from an AST ClassDef node."""
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(base.attr)

        ci = ClassInfo(
            name=node.name,
            module_name=module_name,
            filepath=filepath,
            bases=bases,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            docstring=ast.get_docstring(node) or "",
        )

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                ci.methods[item.name] = item
                ci.method_names.append(item.name)
            elif isinstance(item, (ast.Assign, ast.AnnAssign)):
                targets = []
                if isinstance(item, ast.Assign):
                    targets = item.targets
                elif isinstance(item, ast.AnnAssign) and item.target:
                    targets = [item.target]
                for t in targets:
                    if isinstance(t, ast.Name):
                        ci.class_attributes.add(t.id)

        # Extract instance attributes from __init__
        if '__init__' in ci.methods:
            init_method = ci.methods['__init__']
            for stmt in ast.walk(init_method):
                if isinstance(stmt, ast.Assign):
                    for t in stmt.targets:
                        if isinstance(t, ast.Attribute):
                            if isinstance(t.value, ast.Name) and t.value.id == 'self':
                                ci.instance_attributes.add(t.attr)
                elif isinstance(stmt, ast.AnnAssign):
                    t = stmt.target
                    if isinstance(t, ast.Attribute):
                        if isinstance(t.value, ast.Name) and t.value.id == 'self':
                            ci.instance_attributes.add(t.attr)

        return ci

    def _build_index(self):
        self._class_by_name = {c.name: c for c in self.classes}

    def _find_class(self, name: str) -> Optional[ClassInfo]:
        if name in self._class_by_name:
            return self._class_by_name[name]
        for c in self.classes:
            if c.name == name:
                return c
        return None

    def _method_exists(self, cls: ClassInfo, pattern: str) -> bool:
        pat = re.compile(pattern, re.IGNORECASE)
        return any(pat.search(m) for m in cls.method_names)

    def _methods_matching(self, cls: ClassInfo, pattern: str) -> List[str]:
        pat = re.compile(pattern, re.IGNORECASE)
        return [m for m in cls.method_names if pat.search(m)]

    # ---- Detectors ----

    def _detect_repository(self) -> List[DetectedPattern]:
        """Detect Repository pattern: data access abstraction with CRUD."""
        patterns = []

        for cls in self.classes:
            score = 0.0
            evidence: List[PatternEvidence] = []

            # CRUD operations (prefix-based, matches add_xxx, create_xxx, etc.)
            crud_methods = []
            for mname in cls.method_names:
                if mname.startswith('_') and not mname.startswith('__'):
                    continue
                if re.match(r'^(add_|create_|insert_|save_|new_|register_|add$|create$|register$)',
                            mname, re.IGNORECASE):
                    crud_methods.append((mname, 'C'))
                elif re.match(r'^(get_|find_|query_|lookup_|search_|list_|all_|fetch_|count_|exists_|'
                               r'get$|find$|list$|all$|fetch$|count$|exists$)',
                               mname, re.IGNORECASE):
                    crud_methods.append((mname, 'R'))
                elif re.match(r'^(update_|modify_|set_|change_|edit_|update$|modify$|set$)',
                            mname, re.IGNORECASE):
                    crud_methods.append((mname, 'U'))
                elif re.match(r'^(delete_|remove_|destroy_|cancel_|deactivate_|close_|'
                               r'delete$|remove$|cancel$|close$|deactivate$)',
                               mname, re.IGNORECASE):
                    crud_methods.append((mname, 'D'))

            crud_types = set(t for _, t in crud_methods)

            if len(crud_methods) >= 3:
                score += 0.25
                evidence.append(PatternEvidence(
                    description=f"CRUD methods ({len(crud_methods)}): covers {len(crud_types)} of 4 operations",
                    filepath=cls.filepath,
                    evidence_type="method",
                ))

            # Dict/list storage for data
            storage_attrs = [a for a in cls.instance_attributes
                             if re.search(r'(_dict|_list|_store|_data|_items|_records|_map|_table|s$)',
                                          a, re.IGNORECASE)]
            if not storage_attrs:
                # Also check for plural nouns as storage
                storage_attrs = [a for a in cls.instance_attributes
                                 if a.endswith('s') and len(a) > 3]

            if len(storage_attrs) >= 1 and len(crud_methods) >= 3:
                score += 0.25
                evidence.append(PatternEvidence(
                    description=f"Internal data storage: {', '.join(storage_attrs[:4])}",
                    filepath=cls.filepath,
                    evidence_type="structure",
                ))

            # Naming: Manager, Repository, Storage, Store, Registry, DAO
            name_score = 0.0
            if re.search(r'Repository$', cls.name):
                name_score = 0.3
            elif re.search(r'(Storage|Store|DAO|DataAccess|Registry)$', cls.name):
                name_score = 0.25
            elif re.search(r'Manager$', cls.name) and len(crud_methods) >= 3:
                name_score = 0.25

            if name_score > 0:
                score += name_score
                evidence.append(PatternEvidence(
                    description=f"Class name '{cls.name}' indicates data management role",
                    filepath=cls.filepath,
                    line_start=cls.start_line,
                    evidence_type="naming",
                ))

            # ID-based access pattern (get_by_id, etc.)
            id_methods = self._methods_matching(cls, r'by_id|get_by|_by_')
            if id_methods and crud_methods:
                score += 0.1
                evidence.append(PatternEvidence(
                    description=f"ID-based lookup methods: {len(id_methods)}",
                    filepath=cls.filepath,
                    evidence_type="method",
                ))

            # Business validation methods (quality signal)
            if self._method_exists(cls, r'(_check|_validate|_verify)') and crud_methods:
                score += 0.1
                evidence.append(PatternEvidence(
                    description="Includes validation logic before data operations",
                    filepath=cls.filepath,
                    evidence_type="structure",
                ))

            if score >= 0.40:
                conf = 'high' if score >= 0.75 else ('medium' if score >= 0.55 else 'low')
                patterns.append(DetectedPattern(
                    pattern_id="repository",
                    pattern_name="Repository Pattern",
                    category="structural",
                    confidence=conf,
                    score=min(score, 1.0),
                    target_type="class",
                    target_name=cls.name,
                    filepath=cls.filepath,
                    description=f"{cls.name} encapsulates data access with CRUD operations and validation",
                    evidence=evidence,
                    related_classes=[cls.name],
                ))

        return patterns

    def _detect_service(self) -> List[DetectedPattern]:
        """Detect Service pattern: stateless business logic facade."""
        patterns = []

        for cls in self.classes:
            score = 0.0
            evidence: List[PatternEvidence] = []

            public_methods = [m for m in cls.method_names if not m.startswith('_')]

            # Service naming
            if re.search(r'Service$', cls.name):
                score += 0.3
                evidence.append(PatternEvidence(
                    description="Class name ends with 'Service'",
                    filepath=cls.filepath,
                    evidence_type="naming",
                ))

            # Orchestration: calls other classes / delegates work
            delegation_count = 0
            for mname, method in cls.methods.items():
                if mname.startswith('__'):
                    continue
                for node in ast.walk(method):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Attribute):
                            # self.<attr>.<method>() = delegation to a composed object
                            if isinstance(node.func.value, ast.Attribute):
                                if (isinstance(node.func.value.value, ast.Name)
                                        and node.func.value.value.id == 'self'):
                                    delegation_count += 1

            if delegation_count >= 4 and len(public_methods) >= 2:
                score += 0.3
                evidence.append(PatternEvidence(
                    description=f"Orchestrates {delegation_count} calls to other components",
                    filepath=cls.filepath,
                    evidence_type="structure",
                ))

            # Facade / coordinator: has several high-level public methods
            if len(public_methods) >= 3:
                # Check if methods are orchestrators (call many sub-methods)
                orchestrating = sum(
                    1 for m in public_methods
                    if m in cls.methods and sum(
                        1 for n in ast.walk(cls.methods[m])
                        if isinstance(n, ast.Call)
                    ) >= 3
                )
                if orchestrating >= 2:
                    score += 0.2
                    evidence.append(PatternEvidence(
                        description=f"{orchestrating} high-level methods delegate to lower-level operations",
                        filepath=cls.filepath,
                        evidence_type="structure",
                    ))

            # Entry point / coordinator role (from call graph tags)
            if 'App' in cls.name or 'Coordinator' in cls.name or 'Facade' in cls.name:
                score += 0.15
                evidence.append(PatternEvidence(
                    description="Class name suggests coordination / facade role",
                    filepath=cls.filepath,
                    evidence_type="naming",
                ))

            # Composes multiple other objects (has many self.xxx managers)
            composed_attrs = [a for a in cls.instance_attributes
                              if any(suffix in a.lower() for suffix in
                                     ('_manager', '_service', '_handler', '_controller'))]
            if len(composed_attrs) >= 2:
                score += 0.15
                evidence.append(PatternEvidence(
                    description=f"Composes {len(composed_attrs)} manager/service objects",
                    filepath=cls.filepath,
                    evidence_type="structure",
                ))

            if score >= 0.45:
                conf = 'high' if score >= 0.7 else ('medium' if score >= 0.55 else 'low')
                patterns.append(DetectedPattern(
                    pattern_id="service",
                    pattern_name="Service / Facade Pattern",
                    category="structural",
                    confidence=conf,
                    score=min(score, 1.0),
                    target_type="class",
                    target_name=cls.name,
                    filepath=cls.filepath,
                    description=f"{cls.name} orchestrates business logic by coordinating lower-level components",
                    evidence=evidence,
                    related_classes=[cls.name],
                ))

        return patterns

    def _detect_factory(self) -> List[DetectedPattern]:
        """Detect Factory / Factory Method / Abstract Factory pattern."""
        patterns = []

        for cls in self.classes:
            score = 0.0
            evidence: List[PatternEvidence] = []

            factory_methods = []
            for mname in cls.method_names:
                if mname.startswith('_'):
                    continue
                if re.match(r'^(create|make|build|generate|new_|add_|register)', mname, re.IGNORECASE):
                    factory_methods.append(mname)

            if not factory_methods:
                continue

            score += 0.2
            evidence.append(PatternEvidence(
                description=f"Factory-like methods: {', '.join(factory_methods[:5])}",
                filepath=cls.filepath,
                evidence_type="method",
            ))

            # Methods have conditional returns based on parameters
            conditional_returns = 0
            for fm in factory_methods[:3]:
                if fm in cls.methods:
                    method = cls.methods[fm]
                    for node in ast.walk(method):
                        if isinstance(node, ast.If):
                            # Check if body contains a return with different creation paths
                            if any(isinstance(s, ast.Return) for s in node.body):
                                conditional_returns += 1
                                break

            if conditional_returns >= 1:
                score += 0.15
                evidence.append(PatternEvidence(
                    description="Conditional creation paths (returns different objects)",
                    filepath=cls.filepath,
                    evidence_type="structure",
                ))

            # Naming
            if re.search(r'(Factory|Builder|Creator)$', cls.name):
                score += 0.3
                evidence.append(PatternEvidence(
                    description="Class name indicates factory / builder role",
                    filepath=cls.filepath,
                    evidence_type="naming",
                ))

            # Multiple factory methods = abstract factory hint
            if len(factory_methods) >= 3:
                score += 0.15
                evidence.append(PatternEvidence(
                    description=f"Multiple factory methods ({len(factory_methods)}) suggests Abstract Factory",
                    filepath=cls.filepath,
                    evidence_type="structure",
                ))

            if score >= 0.4:
                conf = 'high' if score >= 0.7 else ('medium' if score >= 0.5 else 'low')
                subtype = "Abstract Factory" if len(factory_methods) >= 3 else "Factory Method"
                patterns.append(DetectedPattern(
                    pattern_id="factory",
                    pattern_name=f"Factory Pattern ({subtype})",
                    category="creational",
                    confidence=conf,
                    score=min(score, 1.0),
                    target_type="class",
                    target_name=cls.name,
                    filepath=cls.filepath,
                    description=f"{cls.name} encapsulates object creation logic",
                    evidence=evidence,
                    related_classes=[cls.name],
                ))

        return patterns

    def _detect_state(self) -> List[DetectedPattern]:
        """Detect State pattern / FSM: behavior changes with state."""
        patterns = []

        for cls in self.classes:
            score = 0.0
            evidence: List[PatternEvidence] = []

            # State attribute(s)
            state_attrs = [a for a in cls.instance_attributes
                           if re.search(r'(state|status|_status|current_state|phase|stage)',
                                        a, re.IGNORECASE)]
            if state_attrs:
                score += 0.2
                evidence.append(PatternEvidence(
                    description=f"State attributes: {', '.join(state_attrs[:4])}",
                    filepath=cls.filepath,
                    evidence_type="structure",
                ))

            # State constants / enums
            state_constants = [a for a in cls.class_attributes
                               if a.isupper() and re.search(r'(STATUS|STATE|PHASE)', a)]
            if state_constants:
                score += 0.15
                evidence.append(PatternEvidence(
                    description=f"State constants: {', '.join(state_constants[:5])}",
                    filepath=cls.filepath,
                    evidence_type="structure",
                ))

            # State transition methods
            transition_methods = self._methods_matching(
                cls,
                r'^(change_state|set_state|transition|goto|enter_|exit_|approve|reject|cancel|'
                r'start|stop|pause|resume|open|close|submit|publish)'
            )
            if transition_methods:
                score += 0.2
                evidence.append(PatternEvidence(
                    description=f"State transition methods: {', '.join(transition_methods[:5])}",
                    filepath=cls.filepath,
                    evidence_type="method",
                ))

            # State-based dispatch (if/elif on state in multiple methods)
            state_dispatch_count = 0
            for mname, method in cls.methods.items():
                if mname.startswith('__'):
                    continue
                for node in ast.walk(method):
                    if isinstance(node, ast.Compare):
                        if isinstance(node.left, ast.Attribute):
                            if ('state' in node.left.attr.lower()
                                    or 'status' in node.left.attr.lower()):
                                if isinstance(node.left.value, ast.Name) and node.left.value.id == 'self':
                                    state_dispatch_count += 1
                                    break

            if state_dispatch_count >= 2:
                score += 0.2
                evidence.append(PatternEvidence(
                    description=f"State-based branching in {state_dispatch_count} methods",
                    filepath=cls.filepath,
                    evidence_type="structure",
                ))

            # Naming: StateMachine, etc.
            if re.search(r'(StateMachine|FSM|FiniteState|StateManager)', cls.name):
                score += 0.15
                evidence.append(PatternEvidence(
                    description="Class name indicates state machine role",
                    filepath=cls.filepath,
                    evidence_type="naming",
                ))

            # Status/state lifecycle: valid states as class constants
            valid_status = [a for a in cls.class_attributes
                            if re.match(r'^(VALID|ALLOWED|POSSIBLE)_', a)]
            if valid_status:
                score += 0.1
                evidence.append(PatternEvidence(
                    description="Defined set of valid states / statuses",
                    filepath=cls.filepath,
                    evidence_type="structure",
                ))

            if score >= 0.4:
                conf = 'high' if score >= 0.7 else ('medium' if score >= 0.55 else 'low')
                patterns.append(DetectedPattern(
                    pattern_id="state",
                    pattern_name="State Pattern (FSM)",
                    category="behavioral",
                    confidence=conf,
                    score=min(score, 1.0),
                    target_type="class",
                    target_name=cls.name,
                    filepath=cls.filepath,
                    description=f"{cls.name} manages state transitions and state-dependent behavior",
                    evidence=evidence,
                    related_classes=[cls.name],
                ))

        return patterns

    def _detect_singleton(self) -> List[DetectedPattern]:
        """Detect Singleton pattern."""
        patterns = []

        for cls in self.classes:
            score = 0.0
            evidence: List[PatternEvidence] = []

            # Class-level instance attribute
            for attr in cls.class_attributes:
                if attr.lower() in ('_instance', 'instance', '__instance', '_singleton'):
                    score += 0.4
                    evidence.append(PatternEvidence(
                        description=f"Class-level singleton attribute: {attr}",
                        filepath=cls.filepath,
                        line_start=cls.start_line,
                        evidence_type="structure",
                    ))
                    break

            # get_instance / instance class method
            if 'get_instance' in cls.method_names or 'instance' in cls.method_names:
                score += 0.3
                mname = 'get_instance' if 'get_instance' in cls.method_names else 'instance'
                evidence.append(PatternEvidence(
                    description=f"Global access point: {mname}",
                    filepath=cls.filepath,
                    evidence_type="method",
                ))

            # __new__ override
            if '__new__' in cls.method_names:
                score += 0.2
                evidence.append(PatternEvidence(
                    description="Overrides __new__ for instance control",
                    filepath=cls.filepath,
                    evidence_type="structure",
                ))

            # Naming hint
            if 'singleton' in cls.name.lower():
                score += 0.1
                evidence.append(PatternEvidence(
                    description="Class name contains 'Singleton'",
                    filepath=cls.filepath,
                    evidence_type="naming",
                ))

            if score >= 0.4:
                conf = 'high' if score >= 0.7 else ('medium' if score >= 0.5 else 'low')
                patterns.append(DetectedPattern(
                    pattern_id="singleton",
                    pattern_name="Singleton Pattern",
                    category="creational",
                    confidence=conf,
                    score=min(score, 1.0),
                    target_type="class",
                    target_name=cls.name,
                    filepath=cls.filepath,
                    description=f"{cls.name} ensures a single instance with global access",
                    evidence=evidence,
                    related_classes=[cls.name],
                ))

        return patterns

    def _detect_strategy(self) -> List[DetectedPattern]:
        """Detect Strategy pattern: interchangeable algorithm family."""
        patterns = []

        strategy_families = {}
        for cls in self.classes:
            public = sorted(m for m in cls.method_names if not m.startswith('_'))
            for m in public:
                strategy_families.setdefault(m, []).append(cls.name)

        shared_methods = {m: names for m, names in strategy_families.items()
                          if len(set(names)) >= 2}

        for cls in self.classes:
            score = 0.0
            evidence: List[PatternEvidence] = []

            # set_strategy / switch_strategy
            if self._method_exists(cls, r'(set_|switch_|change_).*strategy|strategy'):
                score += 0.25
                evidence.append(PatternEvidence(
                    description="Strategy selection method (set/switch/change strategy)",
                    filepath=cls.filepath,
                    evidence_type="method",
                ))

            # Strategy in class name
            if re.search(r'Strategy', cls.name):
                score += 0.2
                evidence.append(PatternEvidence(
                    description="Class name contains 'Strategy'",
                    filepath=cls.filepath,
                    evidence_type="naming",
                ))

            # Shared interface with other classes (strategy family)
            shared = [m for m in shared_methods
                      if cls.name in shared_methods[m]
                      and not m.startswith('_')]
            if len(shared) >= 2:
                score += 0.3
                related = sorted(set(
                    n for m in shared for n in shared_methods[m] if n != cls.name
                ))
                evidence.append(PatternEvidence(
                    description=f"Shares {len(shared)} methods with: {', '.join(related[:3])}",
                    filepath=cls.filepath,
                    evidence_type="structure",
                ))

            if score >= 0.4:
                conf = 'high' if score >= 0.65 else 'medium'
                patterns.append(DetectedPattern(
                    pattern_id="strategy",
                    pattern_name="Strategy Pattern",
                    category="behavioral",
                    confidence=conf,
                    score=min(score, 1.0),
                    target_type="class",
                    target_name=cls.name,
                    filepath=cls.filepath,
                    description=f"{cls.name} encapsulates an interchangeable algorithm",
                    evidence=evidence,
                    related_classes=[cls.name],
                ))

        return patterns

    def _detect_observer(self) -> List[DetectedPattern]:
        """Detect Observer / Pub-Sub pattern."""
        patterns = []

        for cls in self.classes:
            score = 0.0
            evidence: List[PatternEvidence] = []

            has_sub = self._method_exists(cls, r'subscribe|add_listener|add_observer|register')
            has_unsub = self._method_exists(cls, r'unsubscribe|remove_listener|remove_observer|unregister')
            has_notify = self._method_exists(cls, r'notify|broadcast|publish|emit|dispatch')

            if has_sub:
                score += 0.25
                evidence.append(PatternEvidence(
                    description="Subscribe / register method",
                    filepath=cls.filepath,
                    evidence_type="method",
                ))
            if has_unsub:
                score += 0.2
                evidence.append(PatternEvidence(
                    description="Unsubscribe / remove method",
                    filepath=cls.filepath,
                    evidence_type="method",
                ))
            if has_notify:
                score += 0.25
                evidence.append(PatternEvidence(
                    description="Notify / broadcast method",
                    filepath=cls.filepath,
                    evidence_type="method",
                ))

            # Listener storage
            listener_attrs = [a for a in cls.instance_attributes
                              if re.search(r'listener|observer|subscriber|callback|handler',
                                           a, re.IGNORECASE)]
            if listener_attrs:
                score += 0.2
                evidence.append(PatternEvidence(
                    description=f"Observer storage: {', '.join(listener_attrs[:3])}",
                    filepath=cls.filepath,
                    evidence_type="structure",
                ))

            if re.search(r'(Observer|Publisher|Subscriber|EventBus|EventManager|Dispatcher)', cls.name):
                score += 0.1
                evidence.append(PatternEvidence(
                    description="Class name indicates observer / publisher role",
                    filepath=cls.filepath,
                    evidence_type="naming",
                ))

            if score >= 0.5:
                conf = 'high' if score >= 0.8 else ('medium' if score >= 0.65 else 'low')
                patterns.append(DetectedPattern(
                    pattern_id="observer",
                    pattern_name="Observer Pattern (Pub-Sub)",
                    category="behavioral",
                    confidence=conf,
                    score=min(score, 1.0),
                    target_type="class",
                    target_name=cls.name,
                    filepath=cls.filepath,
                    description=f"{cls.name} maintains and notifies a list of observers",
                    evidence=evidence,
                    related_classes=[cls.name],
                ))

        return patterns

    def _detect_template_method(self) -> List[DetectedPattern]:
        """Detect Template Method pattern."""
        patterns = []

        for cls in self.classes:
            if not cls.bases:
                continue

            score = 0.0
            evidence: List[PatternEvidence] = []

            # Public template method that calls several private step methods
            template_candidates = []
            public_methods = [m for m in cls.method_names if not m.startswith('_')]

            for mname in public_methods:
                if mname in cls.methods:
                    method = cls.methods[mname]
                    called_private = 0
                    for node in ast.walk(method):
                        if isinstance(node, ast.Call):
                            if isinstance(node.func, ast.Attribute):
                                called = node.func.attr
                                if called in cls.method_names and called.startswith('_') and not called.startswith('__'):
                                    called_private += 1
                    if called_private >= 2:
                        template_candidates.append((mname, called_private))

            if template_candidates:
                top, calls = max(template_candidates, key=lambda x: x[1])
                score += 0.3 + min(0.1 * calls, 0.2)
                evidence.append(PatternEvidence(
                    description=f"Template method '{top}' calls {calls} step methods",
                    filepath=cls.filepath,
                    evidence_type="structure",
                ))

            # Inheritance with base class
            if cls.bases:
                base_cls = self._find_class(cls.bases[0])
                if base_cls:
                    base_abstract = {m for m in base_cls.method_names
                                     if m.startswith('_') and not m.startswith('__')}
                    overlap = base_abstract & set(cls.method_names)
                    if overlap:
                        score += 0.2
                        evidence.append(PatternEvidence(
                            description=f"Implements {len(overlap)} step methods from base class",
                            filepath=cls.filepath,
                            evidence_type="inheritance",
                        ))

            if score >= 0.4:
                conf = 'high' if score >= 0.6 else 'medium'
                patterns.append(DetectedPattern(
                    pattern_id="template_method",
                    pattern_name="Template Method Pattern",
                    category="behavioral",
                    confidence=conf,
                    score=min(score, 1.0),
                    target_type="class",
                    target_name=cls.name,
                    filepath=cls.filepath,
                    description=f"{cls.name} defines algorithm steps within a template structure",
                    evidence=evidence,
                    related_classes=[cls.name] + (cls.bases[:1] if cls.bases else []),
                ))

        return patterns

    def _detect_adapter(self) -> List[DetectedPattern]:
        """Detect Adapter / Wrapper pattern."""
        patterns = []

        for cls in self.classes:
            score = 0.0
            evidence: List[PatternEvidence] = []

            if re.search(r'(Adapter|Wrapper|Adaptor)$', cls.name):
                score += 0.35
                evidence.append(PatternEvidence(
                    description="Class name ends with Adapter / Wrapper",
                    filepath=cls.filepath,
                    evidence_type="naming",
                ))

            # Has adaptee attribute
            adaptee_attrs = [a for a in cls.instance_attributes
                             if re.search(r'(adaptee|wrapped|_target|_adaptee|_obj|_original)',
                                          a, re.IGNORECASE)]
            if adaptee_attrs:
                score += 0.25
                evidence.append(PatternEvidence(
                    description=f"Wrapped object reference: {', '.join(adaptee_attrs[:3])}",
                    filepath=cls.filepath,
                    evidence_type="structure",
                ))

            if score >= 0.4:
                conf = 'high' if score >= 0.65 else 'medium'
                patterns.append(DetectedPattern(
                    pattern_id="adapter",
                    pattern_name="Adapter Pattern",
                    category="structural",
                    confidence=conf,
                    score=min(score, 1.0),
                    target_type="class",
                    target_name=cls.name,
                    filepath=cls.filepath,
                    description=f"{cls.name} converts one interface to match client expectations",
                    evidence=evidence,
                    related_classes=[cls.name],
                ))

        return patterns

    def _detect_composite(self) -> List[DetectedPattern]:
        """Detect Composite pattern: tree of uniform objects."""
        patterns = []

        for cls in self.classes:
            score = 0.0
            evidence: List[PatternEvidence] = []

            # Children container
            children_attrs = [a for a in cls.instance_attributes
                              if re.search(r'(children|items|nodes|components|members|parts)',
                                           a, re.IGNORECASE)]
            if children_attrs:
                score += 0.2
                evidence.append(PatternEvidence(
                    description=f"Child / component container: {', '.join(children_attrs[:3])}",
                    filepath=cls.filepath,
                    evidence_type="structure",
                ))

            # Add/remove child methods
            add_remove = self._methods_matching(
                cls,
                r'(add_|remove_|append_|insert_|delete_).*(child|node|item|component|member)'
            )
            if len(add_remove) >= 2:
                score += 0.25
                evidence.append(PatternEvidence(
                    description=f"Child management methods: {', '.join(add_remove[:4])}",
                    filepath=cls.filepath,
                    evidence_type="method",
                ))

            if score >= 0.45:
                conf = 'high' if score >= 0.7 else 'medium'
                patterns.append(DetectedPattern(
                    pattern_id="composite",
                    pattern_name="Composite Pattern",
                    category="structural",
                    confidence=conf,
                    score=min(score, 1.0),
                    target_type="class",
                    target_name=cls.name,
                    filepath=cls.filepath,
                    description=f"{cls.name} represents composite objects in a tree structure",
                    evidence=evidence,
                    related_classes=[cls.name],
                ))

        return patterns


def detect_design_patterns(project_info) -> DesignPatternResult:
    """Convenience function: detect patterns from a project info object."""
    detector = DesignPatternDetector()
    return detector.detect_from_project(project_info)
