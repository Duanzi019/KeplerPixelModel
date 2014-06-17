import kplr
import numpy as np
import matplotlib.pyplot as plt

client = kplr.API()

def findMagNeighor(originTpf, num, offset=0, ccd=True):
    if ccd:
        starsOver = client.target_pixel_files(ktc_kepler_id="!=%d"%originTpf.ktc_kepler_id, kic_kepmag=">=%f"%originTpf.kic_kepmag, sci_data_quarter=originTpf.sci_data_quarter, sci_channel=originTpf.sci_channel, sort=("kic_kepmag", 1),ktc_target_type="LC", max_records=num+offset)
        starsUnder = client.target_pixel_files(ktc_kepler_id="!=%d"%originTpf.ktc_kepler_id, kic_kepmag="<=%f"%originTpf.kic_kepmag, sci_data_quarter=originTpf.sci_data_quarter, sci_channel=originTpf.sci_channel, sort=("kic_kepmag", -1),ktc_target_type="LC", max_records=num+offset)
    else:
        starsOver = client.target_pixel_files(ktc_kepler_id="!=%d"%originTpf.ktc_kepler_id, kic_kepmag=">=%f"%originTpf.kic_kepmag, sci_data_quarter=originTpf.sci_data_quarter, sci_channel="!=%d"%originTpf.sci_channel, sort=("kic_kepmag", 1),ktc_target_type="LC", max_records=num+offset)
        starsUnder = client.target_pixel_files(ktc_kepler_id="!=%d"%originTpf.ktc_kepler_id, kic_kepmag="<=%f"%originTpf.kic_kepmag, sci_data_quarter=originTpf.sci_data_quarter, sci_channel="!=%d"%originTpf.sci_channel, sort=("kic_kepmag", -1),ktc_target_type="LC", max_records=num+offset)
    
    stars = {}
    
    i=0
    j=0
    offsetList =[]
    while len(stars) <num+offset:
        while starsOver[i].ktc_kepler_id in stars:
            i+=1
        tmpOver = starsOver[i]
        while starsUnder[j].ktc_kepler_id in stars:
            j+=1
        tmpUnder = starsUnder[j]
        if tmpOver.kic_kepmag-originTpf.kic_kepmag > originTpf.kic_kepmag-tmpUnder.kic_kepmag:
            stars[tmpUnder.ktc_kepler_id] = tmpUnder
            j+=1
            if len(stars)>offset:
                pass
            else:
                offsetList.append(tmpUnder.ktc_kepler_id)
        elif tmpOver.kic_kepmag-originTpf.kic_kepmag < originTpf.kic_kepmag-tmpUnder.kic_kepmag:
            stars[tmpOver.ktc_kepler_id] = tmpOver
            i+=1
            if len(stars)>offset:
                pass
            else:
                offsetList.append(tmpOver.ktc_kepler_id)
        elif len(stars) < num+offset-1:
            stars[tmpUnder.ktc_kepler_id] = tmpUnder
            stars[tmpOver.ktc_kepler_id] = tmpOver
            i+=1
            j+=1
            if len(stars)>offset+1:
                pass
            elif len(stars) == offset+1:
                offsetList.append(tmpUnder.ktc_kepler_id)
            else:
                offsetList.append(tmpOver.ktc_kepler_id)
                offsetList.append(tmpUnder.ktc_kepler_id)
        else:
            stars[tmpOver.ktc_kepler_id] = tmpOver
            i+=1
            if len(stars)>offset:
                pass
            else:
                offsetList.append(tmpOver.ktc_kepler_id)
    
    for key in offsetList:
        stars.pop(key)
    return stars

def convertData(tdf):
    time, flux = [], []
    with tdf.open() as file:
        hdu_data = file[1].data
        time = hdu_data["time"]
        flux = hdu_data["flux"]
    shape = flux.shape
    flux = flux.reshape((flux.shape[0], -1))
    mask = np.array(np.sum(np.isfinite(flux), axis=0), dtype=bool)
    flux = flux[:, mask]

    for i in range(flux.shape[1]):
        interMask = np.isfinite(flux[:,i])
        flux[~interMask,i] = np.interp(time[~interMask], time[interMask], flux[interMask,i])

    return time, flux, mask, shape

def neighorFit(neighorNum=1, offset=0, ccd=True):
    originStar = client.star(5088536)
    originTpf = client.target_pixel_files(ktc_kepler_id=originStar.kepid, sci_data_quarter=5)[0]
    neighor = findMagNeighor(originTpf, neighorNum, offset, ccd)

    time, targetFlux, targetMask, targetShape = convertData(originTpf)

    neighorKID, neighorFluxes, neighorMaskes, neighorShapes = [], [], [], []

    for key,tpf in neighor.items():
        neighorKID.append(key)
        tmpResult = convertData(tpf)
        neighorFluxes.append(tmpResult[1])
        neighorMaskes.append(tmpResult[2])
        neighorShapes.append(tmpResult[3])
    neighorFluxMatrix = np.concatenate(neighorFluxes, axis=1)

    result  = np.linalg.lstsq(neighorFluxMatrix, targetFlux)

    f, axes = plt.subplots(3, 1)

    axes[0].plot(time, targetFlux[:,10])
    plt.setp( axes[0].get_xticklabels(), visible=False)
    plt.setp( axes[0].get_yticklabels(), visible=False)
    axes[0].set_ylabel("flux of tpf")

    fitFlux = np.dot(neighorFluxMatrix, result[0])
    axes[1].plot(time, fitFlux[:,10])
    plt.setp( axes[1].get_xticklabels(), visible=False)
    plt.setp( axes[1].get_yticklabels(), visible=False)
    axes[1].set_ylabel("flux of fit")

    axes[2].plot(time, np.divide(targetFlux[:,10], fitFlux[:,10]))
    #plt.setp( axes[2].get_xticklabels(), visible=False)
    #plt.setp( axes[2].get_yticklabels(), visible=False)
    axes[2].set_ylim(0.999,1.001)
    axes[2].set_xlabel("time")
    axes[2].set_ylabel("ratio of data and fit")

    plt.subplots_adjust(left=None, bottom=None, right=None, top=None,
                        wspace=0, hspace=0)
    plt.suptitle('Kepler %d Quarter %d Pixel(2,4) \n Fit Source[Initial:%d Number:%d CCD:%r] Total residuals:%f'%(originTpf.ktc_kepler_id, originTpf.sci_data_quarter, offset+1, neighorNum, ccd, result[1][10]))
    plt.savefig('fit(2,4)_%d_%d_ccd%r.png'%(offset+1,neighorNum,ccd))
    plt.clf()

    f = open('coe(2,4)_%d_%d_ccd%r.dat'%(offset+1,neighorNum,ccd), 'w')
    loc = 0
    for n in range(0, neighorNum):
        coe = np.zeros_like(neighorMaskes[n], dtype=float)
        coe = np.ma.masked_equal(coe,0)
        coe[neighorMaskes[n]] = result[0][loc:loc+neighorFluxes[n].shape[1],10]
        loc += neighorFluxes[n].shape[1]
        coe = coe.reshape((neighorShapes[n][1],neighorShapes[n][2]))

        f.write('fit coefficient of the pixels of kepler %d\n'%neighorKID[n])
        f.write('================================================\n')
        for i in range(coe.shape[0]):
            for j in range(coe.shape[1]):
                f.write('%8.5f   '%coe[i,j])
            f.write('\n')
        f.write('================================================\n')
    f.write('Sums of residuals:%f'%result[1][10])
    f.close()
    return result
'''
neighorNum = np.arange(12)+1
residuals = np.empty_like(neighorNum)
for i in neighorNum:
    residuals[i-1] = neighorFit(i,0,True)[1][10]
plt.clf()
plt.plot(neighorNum,residuals,'bs')
plt.xlabel("Number of Neighors")
plt.ylabel("Total squared residuals")
plt.savefig('neighorNum-res.png')
'''
neighorFit(1,0,True)
neighorFit(2,0,True)
neighorFit(1,1,True)
neighorFit(1,0,False)




