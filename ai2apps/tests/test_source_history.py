from ai2apps.intelligence.source_history import other_sources

def test_preserves_sources_beyond_five_versions_without_changing_citations():
    current={'sources':[{'url':'https://cnn.com/a'}]}
    previous={'sources':[{'url':'https://nyt.com/a','coverage':'preview','access_reason':'login_required'}],
      'versions':[{'sources':[{'url':'https://cnn.com/a#top'},{'url':'https://nyt.com/a'}]}],
      'related_sources':[{'url':'https://example.com/early'}]}
    result=other_sources(current,previous)
    assert len(result)==2
    assert result[0]['coverage']=='preview'
    assert result[1]['url']=='https://example.com/early'
    assert current['sources']==[{'url':'https://cnn.com/a'}]
    assert len(other_sources(current,{'sources':current['sources'],'related_sources':result}))==2
