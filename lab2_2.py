from onvif import ONVIFCamera
import urllib2
import requests
import cv2
import matplotlib.pyplot as plt
import time
from threading import Thread
import numpy

def drawAxis(axis, values, color):
	axis.cla()
	axis.plot(values, color)
	axis.set_xlim(0, 255)
	axis.set_yticklabels([])

def calculateMove(values, coef, accur, maxStep):
	values = [i[0] for i in values]
	if values[0] >= values[1]:
		max = 0
		min = 1
		moveTo = 1
	else:
		max = 1
		min = 0
		moveTo = -1
	if values[max] * accur > values[min]:
		move = (1 - (values[min] / values[max])) * coef * maxStep
		move *= moveTo
		return move
	return 0

def createImagingRequest(imaging, token):
	requestSetImagingSettings = imaging.create_type("SetImagingSettings")
	requestSetImagingSettings.VideoSourceToken = token
	requestSetImagingSettings.ImagingSettings = imaging.GetImagingSettings({'VideoSourceToken': token})
	return requestSetImagingSettings

def downloadImage(media_service, media_profile, login, password, filename):
	previewUri = media_service.GetSnapshotUri({'ProfileToken': media_profile._token}).Uri

	manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
	manager.add_password(None, previewUri, login, password)

	auth = urllib2.HTTPBasicAuthHandler(manager)

	opener = urllib2.build_opener(auth)
	urllib2.install_opener(opener)
	imageFromCamera = urllib2.urlopen(previewUri)
	buf = imageFromCamera.read()
	downloadedImage = open(filename, "wb")
	downloadedImage.write(buf)
	downloadedImage.close()
	imageFromCamera.close()	

def setContrast(imaging, token, value):
	request = createImagingRequest(imaging, token)
	request.ImagingSettings.Contrast = relativeSum(0, 100, value, request.ImagingSettings.Contrast)
	imaging.SetImagingSettings(request)

def setBrightness(imaging, token, value):
	request = createImagingRequest(imaging, token)
	request.ImagingSettings.Brightness = relativeSum(0, 100, value, request.ImagingSettings.Brightness)
	imaging.SetImagingSettings(request)

def setExposure(imaging, token, value):
	request = createImagingRequest(imaging, token)
	try:
		request.ImagingSettings.Exposure.Gain = relativeSum(0, 100, value, request.ImagingSettings.Exposure.Gain)
		imaging.SetImagingSettings(request)
	except Exception as e:
		setBrightness(imaging, token, value)

def setExposureTime(imaging, token, value):
	request = createImagingRequest(imaging, token)
	request.ImagingSettings.Exposure.ExposureTime = relativeSum(0, 40000, value, request.ImagingSettings.Exposure.ExposureTime)
	imaging.SetImagingSettings(request)

def setCrGain(imaging, token, value):
	request = createImagingRequest(imaging, token)
	request.ImagingSettings.WhiteBalance.CrGain = relativeSum(0, 255, value, request.ImagingSettings.WhiteBalance.CrGain)
	imaging.SetImagingSettings(request)

def setCbGain(imaging, token, value):
	request = createImagingRequest(imaging, token)
	request.ImagingSettings.WhiteBalance.CbGain = relativeSum(0, 255, value, request.ImagingSettings.WhiteBalance.CbGain)
	imaging.SetImagingSettings(request)

def relativeSum(min, max, relative, current):
	current += relative
	if(current < min):
		return min
	if(current > max):
		return max
	return current

def isNeedToStop(array):
	perc = numpy.percentile(array, [5, 95])
	print perc
	return perc[0] > 200 and perc[0] < 1000 and perc[1] < 40000 and perc[1] > 15000
	
	
def findFirstExtraFromLeftIndex(hist_y_6):
	leftIndex = len(hist_y_6) - 1
	for i in range(1, len(hist_y_6)):
		if hist_y_6[i][0] > 300000:
			leftIndex = i
			break
	return leftIndex

def findFirstExtraFromRightIndex(hist_y_6):
	rightIndex = 1
	for i in range(len(hist_y_6) - 1, 0, -1):
		if hist_y_6[i][0] > 300000:
			rightIndex = i
			break
	return rightIndex
	
def increaseExp(imaging, token, hist_y_6, w):
	dif = (len(hist_y_6) - w) * 20.0 / len(hist_y_6)
	dif = round(dif)
	print('exp +', dif)
	setExposure(imaging, token, dif)

def decreaseExp(imaging, token, hist_y_6, b):
	dif = b * 20.0 / len(hist_y_6)
	dif = round(dif)
	print('exp -', dif)
	setExposure(imaging, token, -dif)


def increaseContrast(imaging, token, hist_y_6, w, b):
	val = min(b, len(hist_y_6) - w)
	dif = val * 20.0 / (len(hist_y_6) / 2.0)
	dif = round(dif)
	print('contrast +', dif)
	setContrast(imaging, token, dif)

def decreaseContrast(imaging, token, hist_y_6):
	val = max(hist_y_6[0][0], hist_y_6[-1][0])
	dif = val / 2000000.0 * 20.0
	dif = round(dif)
	print('contrast -', dif)
	setContrast(imaging, token, -dif)

	
def adjustCamera(ip, port, login, password) :
	mycam = ONVIFCamera(ip, port, login, password, 'C:\Python27\wsdl')
	media_service = mycam.create_media_service()
	media_profile = media_service.GetProfiles()[0]
	imaging = mycam.create_imaging_service()
	token = media_profile.VideoSourceConfiguration.SourceToken

	request = createImagingRequest(imaging, token)
	try:
		request.ImagingSettings.Exposure.Mode = 'MANUAL'
	except Exception as e:
		print 'exposureMode can not bo MANUAL'
	try:
		request.ImagingSettings.WhiteBalance.Mode = 'MANUAL'
	except Exception as e:
		print 'whiteBalanceMode can not be MANUAL'
	try:
		imaging.SetImagingSettings(request)
	except Exception as e:
		print 'error'

	while True:
		filename = ip + '.jpg'
		downloadImage(media_service, media_profile, login, password, filename)

		im = cv2.imread(filename)

		ycbcr = cv2.cvtColor(im, cv2.COLOR_BGR2YCrCb)

		hist_y = cv2.calcHist([ycbcr],[0],None,[256],[0,256])
		hist_cr = cv2.calcHist([ycbcr],[1],None,[256],[0,256])
		hist_cb = cv2.calcHist([ycbcr],[2],None,[256],[0,256])

		hist_cb_2 = cv2.calcHist([ycbcr],[2],None,[2],[0,256])
		hist_cr_2 = cv2.calcHist([ycbcr],[1],None,[2],[0,256])


		hist_y_6 = cv2.calcHist([ycbcr], [0], None, [6], [0,256])

		if not isNeedToStop(hist_y):
			leftIndex = findFirstExtraFromLeftIndex(hist_y_6)
			rightIndex = findFirstExtraFromRightIndex(hist_y_6)

			black = hist_y_6[0][0] > 300000
			white = hist_y_6[-1][0] > 300000
			if black and white:
				decreaseContrast(imaging, token, hist_y_6)
			elif black:
				increaseExp(imaging, token, hist_y_6, rightIndex)
			elif white:
				decreaseExp(imaging, token, hist_y_6, leftIndex)
			else:
				increaseContrast(imaging, token, hist_y_6, rightIndex, leftIndex)

		try:
			Cb = calculateMove(hist_cb_2, 2.56, 0.9, 2)
			print('Cb:', Cb)
			setCbGain(imaging, token, Cb)
			Cr = calculateMove(hist_cr_2, 2.56, 0.9, 2)
			print('Cr:', Cr)
			setCrGain(imaging, token, Cr)
		except Exception as e:
			print 'WhiteBalance error'

		time.sleep(1)
		
if __name__ == '__main__':
	thread42 = Thread(target=adjustCamera, args=('192.168.15.42', 80, 'admin', 'Supervisor'))
	thread42.start()
	thread43 = Thread(target=adjustCamera, args=('192.168.15.43', 80, 'admin', 'Supervisor'))
	thread43.start()
	
	

