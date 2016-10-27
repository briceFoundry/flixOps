import os

_editorialAnnotation = None
def EditorialAnnotation():
    global _editorialAnnotation
    if _editorialAnnotation is None:
        config = os.environ['FLIX_EDITORIAL_ANNOTATION']
        configClass = config.split('.')[-1]
        configModule = '.'.join(config.split('.')[0:-1])
        tmp = __import__(configModule, globals(), locals(), [configClass], -1)
        _editorialAnnotation = getattr(tmp, configClass)()
    return _editorialAnnotation


_flixNuke = None
def FlixNuke():
    global _flixNuke
    if _flixNuke is None:
        config = os.environ['FLIX_NUKE']
        configClass = config.split('.')[-1]
        configModule = '.'.join(config.split('.')[0:-1])
        tmp = __import__(configModule, globals(), locals(), [configClass], -1)
        _flixNuke = getattr(tmp, configClass)()
    return _flixNuke
