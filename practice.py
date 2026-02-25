import OpenDartReader
api_key = ''
dart = OpenDartReader(api_key) 


result = dart.company('005930')
print(result)