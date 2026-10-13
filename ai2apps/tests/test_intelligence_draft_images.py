import pytest
from ai2apps.intelligence.writing import DraftImages, place_images

def test_placements_validate_source_and_post_position():
    draft={'channel_id':'c','kind':'long_article','evidence':[{'id':'a'}],'current':{'content':'First\n\nSecond'}}
    articles=[{'id':'a','channel_id':'c','images':[{'url':'https://example.com/image.jpg','alt':'Image'}]}]
    def body(before='',article_id='a'):
        return DraftImages(revision=1,images=[{'url':'https://example.com/image.jpg','article_id':article_id,'before':before}])
    assert place_images(draft,articles,body('Second'))[0]['before']=='Second'
    with pytest.raises(ValueError):place_images(draft,articles,body('Missing'))
    with pytest.raises(ValueError):place_images(draft,articles,body(article_id='foreign'))
    draft['kind']='short_post'
    with pytest.raises(ValueError):place_images(draft,articles,body('First'))
    assert place_images(draft,articles,body())[0]['before']==''
