import importlib.util
from pathlib import Path
def runner():
    p=Path(__file__).resolve().parents[1]/'scripts/run_factor_ablation.py'
    spec=importlib.util.spec_from_file_location('factor_test_runner',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def test_all_activities_retained_and_unknown_not_a_factor():
    m=runner();groups,n=m.activity_groups({'known_activities':[
      {'activity':'Software subscriptions','role':'software_provider','facets':{'customer':'unknown','revenue_model':'subscriptions'}},
      {'activity':'Hardware manufacturing','role':'producer','facets':{'product_type':'Industrial sensors','customer':'factories'}}]})
    assert groups['product']=='Software subscriptions; Industrial sensors'
    assert groups['customer']=='factories'
    assert groups['role']=='software provider; producer'
    assert n==1
def test_missing_is_empty_not_a_shared_unknown_group():
    m=runner();groups,n=m.activity_groups({'known_activities':[{'activity':'Business A','role':'unknown','facets':{'customer':'not stated'}}]})
    assert groups['role']==groups['customer']==''
    assert groups['product']=='Business A'
