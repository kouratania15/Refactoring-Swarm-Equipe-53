#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de test simple pour tester les agents individuellement.
Utilisation : python test_agents.py
"""

import sys
import os
from pathlib import Path

# Fix UTF-8 encoding on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Configuration Python path
sys.path.insert(0, str(Path(__file__).parent))
os.environ['PYTHONIOENCODING'] = 'utf-8'

from dotenv import load_dotenv
from src.agents.auditor_agent import AuditorAgent
from src.agents.fixer_agent import FixerAgent
from src.agents.judge_agent import JudgeAgent

load_dotenv()


def test_auditor_agent():
    """Test l'agent Auditor seul."""
    print("\n" + "="*70)
    print("TEST 1: AUDITOR AGENT (Analyse du code)")
    print("="*70)
    
    try:
        auditor = AuditorAgent()
        target_dir = Path("sandbox/test_code")
        
        print(f"\nAnalyse du dossier: {target_dir.resolve()}")
        result = auditor.analyze(target_dir)
        
        print(f"\nResultats:")
        print(f"  - Problemes detectes: {result['issues_found']}")
        print(f"  - Fichiers analyses: {len(result['files_analyzed'])}")
        print(f"  - Plan de corrections: {len(result['plan'])} fichier(s)")
        
        if result['plan']:
            for file_path, issues in result['plan'].items():
                print(f"\n  Fichier: {Path(file_path).name}")
                print(f"  Problemes ({len(issues)}):")
                for i, issue in enumerate(issues[:3], 1):
                    print(f"    {i}. {issue[:80]}...")
        
        return result
    
    except Exception as e:
        print(f"\nERREUR: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_fixer_agent():
    """Test l'agent Fixer seul."""
    print("\n" + "="*70)
    print("TEST 2: FIXER AGENT (Correction du code)")
    print("="*70)
    
    # D'abord faire une analyse
    print("\n1. Etape analyse (Auditor)...")
    audit_result = test_auditor_agent()
    
    if not audit_result or not audit_result['plan']:
        print("\nPas de problemes a corriger.")
        return
    
    try:
        fixer = FixerAgent()
        target_dir = Path("sandbox/test_code")
        
        print(f"\n2. Etape correction (Fixer)...")
        print(f"   Correction de {len(audit_result['plan'])} fichier(s)...")
        
        fix_result = fixer.fix_issues(target_dir, audit_result['plan'])
        
        print(f"\nResultats:")
        print(f"  - Fichiers modifies: {fix_result['files_modified']}")
        print(f"  - Changements appliques: {len(fix_result['changes_applied'])}")
        for change in fix_result['changes_applied']:
            print(f"    • {change}")
        
        return fix_result
    
    except Exception as e:
        print(f"\nERREUR: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_judge_agent():
    """Test l'agent Judge seul."""
    print("\n" + "="*70)
    print("TEST 3: JUDGE AGENT (Validation par tests)")
    print("="*70)
    
    try:
        judge = JudgeAgent()
        target_dir = Path("sandbox/test_code")
        
        print(f"\nExecution des tests: {target_dir.resolve()}")
        result = judge.run_tests(target_dir)
        
        print(f"\nResultats:")
        print(f"  - Tests executes: {result['total_tests']}")
        print(f"  - Tests reussis: {result['passed']}")
        print(f"  - Tests echoues: {result['failures']}")
        print(f"  - Tous passent: {'OUI' if result['all_passed'] else 'NON'}")
        
        if result['error_logs']:
            print(f"\n  Logs (premiere 500 chars):")
            print(f"  {result['error_logs'][:500]}")
        
        return result
    
    except Exception as e:
        print(f"\nERREUR: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_full_cycle():
    """Test le cycle complet: Audit -> Fix -> Judge."""
    print("\n" + "="*70)
    print("TEST COMPLET: CYCLE AUDIT -> FIX -> JUDGE")
    print("="*70)
    
    print("\n[ETAPE 1] AUDIT DU CODE")
    audit_result = test_auditor_agent()
    
    if audit_result and audit_result['plan']:
        print("\n[ETAPE 2] CORRECTION DU CODE")
        fix_result = test_fixer_agent()
        
        print("\n[ETAPE 3] VALIDATION PAR TESTS")
        judge_result = test_judge_agent()
        
        print("\n" + "="*70)
        print("RESUME FINAL")
        print("="*70)
        print(f"Problemes detentes: {audit_result['issues_found']}")
        print(f"Fichiers corriges: {fix_result['files_modified'] if fix_result else 0}")
        print(f"Tests: {judge_result['passed']}/{judge_result['total_tests']} passes" if judge_result else "Erreur tests")
    else:
        print("\nCode est clean, aucune correction necessaire!")


if __name__ == "__main__":
    print("\nTEST DES AGENTS REFACTORING SWARM")
    print("="*70)
    
    # Vous pouvez tester un agent a la fois ou le cycle complet
    # test_auditor_agent()        # Tester Auditor seul
    # test_fixer_agent()          # Tester Fixer seul
    # test_judge_agent()          # Tester Judge seul
    test_full_cycle()              # Tester le cycle complet
    
    print("\n" + "="*70)
    print("TESTS TERMINES")
    print("="*70)
