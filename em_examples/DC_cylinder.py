#import sys
#sys.path.append("./simpeg")
#sys.path.append("./simpegdc/")

#import warnings
#warnings.filterwarnings('ignore')

from SimPEG import Mesh, Maps, SolverLU, Utils
import SimPEG.Utils as Utils
from SimPEG.Utils import ExtractCoreMesh
import numpy as np
from SimPEG.EM.Static import DC
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.pylab as pylab
from matplotlib.ticker import LogFormatter 


import warnings
warnings.filterwarnings('ignore') # ignore warnings: only use this once you are sure things are working

try:
    from IPython.html.widgets import  interact, IntSlider, FloatSlider, FloatText, ToggleButtons
    pass
except Exception, e:    
    from ipywidgets import interact, IntSlider, FloatSlider, FloatText, ToggleButtons

# Mesh, sigmaMap can be globals global
npad = 15
growrate = 2.
cs = 0.5
hx = [(cs,npad, -growrate),(cs,200),(cs,npad, growrate)]
hy = [(cs,npad, -growrate),(cs,100)]
mesh = Mesh.TensorMesh([hx, hy], "CN")
circmap = Maps.CircleMap(mesh)
idmap = Maps.IdentityMap(mesh)
circmap.slope = 1e16
sigmaMap = idmap
dx = 5 
xr = np.arange(-40,41,dx)
dxr = np.diff(xr)
xmin = -40.
xmax = 40.
ymin = -40.
ymax = 5.
xylim = np.c_[[xmin,ymin],[xmax,ymax]]
indCC, meshcore = ExtractCoreMesh(xylim,mesh)
indx = (mesh.gridFx[:,0]>=xmin) & (mesh.gridFx[:,0]<=xmax) \
    & (mesh.gridFx[:,1]>=ymin) & (mesh.gridFx[:,1]<=ymax)
indy = (mesh.gridFy[:,0]>=xmin) & (mesh.gridFy[:,0]<=xmax) \
    & (mesh.gridFy[:,1]>=ymin) & (mesh.gridFy[:,1]<=ymax)
indF = np.concatenate((indx,indy))


def cylinder_fields(A,B,r,sigcyl,sighalf,xc=0.,yc=-20.):

    circhalf = np.r_[np.log(sighalf), np.log(sighalf), xc, yc, r]
    circtrue = np.r_[np.log(sigcyl), np.log(sighalf), xc, yc, r]
    
    mhalf = circmap*circhalf
    mtrue = circmap*circtrue
    
    Mx = np.empty(shape=(0, 2))
    Nx = np.empty(shape=(0, 2))
    #rx = DC.Rx.Dipole_ky(Mx,Nx)
    rx = DC.Rx.Dipole(Mx,Nx)
    if(B == []):
        src = DC.Src.Pole([rx], np.r_[A,0.])
    else:
        src = DC.Src.Dipole([rx], np.r_[A,0.], np.r_[B,0.])
    #survey = DC.Survey_ky([src])
    survey = DC.Survey([src])
    survey_prim = DC.Survey([src])
    #problem = DC.Problem2D_CC(mesh, sigmaMap = sigmaMap)
    problem = DC.Problem3D_CC(mesh, sigmaMap = sigmaMap)
    problem_prim = DC.Problem3D_CC(mesh, sigmaMap = sigmaMap)
    problem.Solver = SolverLU
    problem_prim.Solver = SolverLU
    problem.pair(survey)
    problem_prim.pair(survey_prim)

    primary_field = problem_prim.fields(mhalf)
    #phihalf = f[src, 'phi', 15]
    #ehalf = f[src, 'e']
    #jhalf = f[src, 'j']
    #charge = f[src, 'charge']

    total_field = problem.fields(mtrue)
    #phi = f[src, 'phi', 15]
    #e = f[src, 'e']
    #j = f[src, 'j']
    #charge = f[src, 'charge']

    return mtrue,mhalf, src, total_field, primary_field


def get_Surface_Potentials(survey, src,field_obj):

    phi = field_obj[src, 'phi']
    CCLoc = mesh.gridCC
    zsurfaceLoc = np.max(CCLoc[:,1])
    surfaceInd = np.where(CCLoc[:,1] == zsurfaceLoc)
    xSurface = CCLoc[surfaceInd,0].T
    phiSurface = phi[surfaceInd]
    phiScale = 0.

    if(survey == "Pole-Dipole" or survey == "Pole-Pole"):
        refInd = Utils.closestPoints(mesh, [xmax+60.,0.], gridLoc='CC')
        # refPoint =  CCLoc[refInd]
        # refSurfaceInd = np.where(xSurface == refPoint[0])
        # phiScale = np.median(phiSurface)
        phiScale = phi[refInd]
        phiSurface = phiSurface - phiScale

    return xSurface,phiSurface,phiScale


# Inline functions for computing apparent resistivity
eps = 1e-9 #to stabilize division
G = lambda A, B, M, N: 1. / ( 1./(np.abs(A-M)+eps) - 1./(np.abs(M-B)+eps) - 1./(np.abs(N-A)+eps) + 1./(np.abs(N-B)+eps) )
rho_a = lambda VM,VN, A,B,M,N: (VM-VN)*2.*np.pi*G(A,B,M,N)

def getSensitivity(survey,A,B,M,N,model):

    if(survey == "Dipole-Dipole"):
        rx = DC.Rx.Dipole(np.r_[M,0.], np.r_[N,0.])
        src = DC.Src.Dipole([rx], np.r_[A,0.], np.r_[B,0.])
    elif(survey == "Pole-Dipole"):
        rx = DC.Rx.Dipole(np.r_[M,0.], np.r_[N,0.])
        src = DC.Src.Pole([rx], np.r_[A,0.])
    elif(survey == "Dipole-Pole"):
        rx = DC.Rx.Pole(np.r_[M,0.])
        src = DC.Src.Dipole([rx], np.r_[A,0.], np.r_[B,0.])
    elif(survey == "Pole-Pole"):
        rx = DC.Rx.Pole(np.r_[M,0.])
        src = DC.Src.Pole([rx], np.r_[A,0.])

    survey = DC.Survey([src])
    problem = DC.Problem3D_CC(mesh, sigmaMap = sigmaMap)
    problem.Solver = SolverLU
    problem.pair(survey)
    fieldObj = problem.fields(model)

    J = problem.Jtvec(model, np.array([1.]), f=fieldObj)

    return J

def calculateRhoA(survey,VM,VN,A,B,M,N):

    eps = 1e-9 #to stabilize division

    if(survey == "Dipole-Dipole"):
        G =  1. / ( 1./(np.abs(A-M)+eps) - 1./(np.abs(M-B)+eps) - 1./(np.abs(N-A)+eps) + 1./(np.abs(N-B)+eps) )
        rho_a = (VM-VN)*2.*np.pi*G
    elif(survey == "Pole-Dipole"):
        G =  1. / ( 1./(np.abs(A-M)+eps) - 1./(np.abs(N-A)+eps) )
        rho_a = (VM-VN)*2.*np.pi*G
    elif(survey == "Dipole-Pole"):
        G =  1. / ( 1./(np.abs(A-M)+eps) - 1./(np.abs(M-B)+eps) )
        rho_a = (VM)*2.*np.pi*G
    elif(survey == "Pole-Pole"):
        G =  1. / ( 1./(np.abs(A-M)+eps) )
        rho_a = (VM)*2.*np.pi*G

    return rho_a

def plot_Surface_Potentials(survey,A,B,M,N,r,xc,yc,rhohalf,rhocyl,Field,Type):

    labelsize = 18.
    ticksize = 16.

    sigcyl = 1./rhocyl
    sighalf = 1./rhohalf

    if(survey == "Pole-Dipole" or survey == "Pole-Pole"):
        B = []

    mtrue, mhalf, src, total_field, primary_field = cylinder_fields(A,B,r,sigcyl,sighalf,xc,yc)

    fig, ax = plt.subplots(2,1,figsize=(8*1.5,8.5*1.5),sharex=True)
    fig.subplots_adjust(right=0.8)

    xSurface, phiTotalSurface, phiScaleTotal = get_Surface_Potentials(survey, src, total_field)
    xSurface, phiPrimSurface, phiScalePrim = get_Surface_Potentials(survey, src, primary_field)
    ylim = np.r_[-1., 1.]*np.max(np.abs(phiTotalSurface))
    xlim = np.array([-40,40])

    if(survey == "Dipole-Pole" or survey == "Pole-Pole"):
        MInd = np.where(xSurface == M)
        N = []

        VM = phiTotalSurface[MInd[0]]
        VN = 0.

        VMprim = phiPrimSurface[MInd[0]]
        VNprim = 0.

    else:
        MInd = np.where(xSurface == M)
        NInd = np.where(xSurface == N)

        VM = phiTotalSurface[MInd[0]]
        VN = phiTotalSurface[NInd[0]]

        VMprim = phiPrimSurface[MInd[0]]
        VNprim = phiPrimSurface[NInd[0]]

    #2D geometric factor
    G2D = rhohalf/(calculateRhoA(survey,VMprim,VNprim,A,B,M,N))

    # Subplot 1: Full set of surface potentials
    ax[0].plot(xSurface,phiTotalSurface,color=[0.1,0.5,0.1],linewidth=2)
    ax[0].plot(xSurface,phiPrimSurface ,linestyle='dashed',linewidth=0.5,color='k')
    ax[0].grid(which='both',linestyle='-',linewidth=0.5,color=[0.2,0.2,0.2],alpha=0.5)
    
    if(survey == "Pole-Dipole" or survey == "Pole-Pole"):
        ax[0].plot(A,0,'+',markersize = 12, markeredgewidth = 3, color=[1.,0.,0])
    else:
        ax[0].plot(A,0,'+',markersize = 12, markeredgewidth = 3, color=[1.,0.,0])
        ax[0].plot(B,0,'_',markersize = 12, markeredgewidth = 3, color=[0.,0.,1.])
    ax[0].set_ylabel('Potential, (V)',fontsize = labelsize)
    ax[0].set_xlabel('x (m)',fontsize = labelsize)
    ax[0].set_xlim(xlim)
    ax[0].set_ylim(ylim)

    if(survey == "Dipole-Pole" or survey == "Pole-Pole"):
        ax[0].plot(M,VM,'o',color='k')

        xytextM = (M+0.5,np.max([np.min([VM,ylim.max()]),ylim.min()])+0.5)
        ax[0].annotate('%2.1e'%(VM), xy=xytextM, xytext=xytextM,fontsize = labelsize)

    else:
        ax[0].plot(M,VM,'o',color='k')
        ax[0].plot(N,VN,'o',color='k')

        xytextM = (M+0.5,np.max([np.min([VM,ylim.max()]),ylim.min()])+0.5)
        xytextN = (N+0.5,np.max([np.min([VN,ylim.max()]),ylim.min()])+0.5)
        ax[0].annotate('%2.1e'%(VM), xy=xytextM, xytext=xytextM,fontsize = labelsize)
        ax[0].annotate('%2.1e'%(VN), xy=xytextN, xytext=xytextN,fontsize = labelsize)

    ax[0].tick_params(axis='both', which='major', labelsize=ticksize)

    props = dict(boxstyle='round', facecolor='grey', alpha=0.4)
    ax[0].text(xlim.max()+1,ylim.max()-0.1*ylim.max(),'$\\rho_a$ = %2.2f'%(G2D*calculateRhoA(survey,VM,VN,A,B,M,N)),
                verticalalignment='bottom', bbox=props, fontsize = labelsize)

    ax[0].legend(['Model Potential','Half-Space Potential'], loc=3, fontsize = labelsize)

    #Subplot 2: Fields
    ax[1].plot(np.arange(-r,r+r/10,r/10)+xc,np.sqrt(-np.arange(-r,r+r/10,r/10)**2.+r**2.)+yc,linestyle = 'dashed',color='k')
    ax[1].plot(np.arange(-r,r+r/10,r/10)+xc,-np.sqrt(-np.arange(-r,r+r/10,r/10)**2.+r**2.)+yc,linestyle = 'dashed',color='k')

    if Field == 'Model':

        label = 'Resisitivity (ohm-m)'
        xtype = 'CC'
        view = 'real'
        streamOpts = None
        ind = indCC

        formatter = "1e%.1f"
        pcolorOpts = {"cmap":"jet_r"}


        if Type == 'Total':
            u = 1./(mtrue)
            u = np.log10(u)
        elif Type == 'Primary':
            u = 1./(mhalf)
            u = np.log10(u)
        elif Type == 'Secondary':
            u = 1./(mtrue) - 1./(mhalf)
            formatter = "%.1e"
            pcolorOpts = {"cmap":"jet_r"}


    elif Field == 'Potential':

        label = 'Potential (V)'
        xtype = 'CC'
        view = 'real'
        streamOpts = None
        ind = indCC

        formatter = "%.1e"
        pcolorOpts = {"cmap":"viridis"}

        if Type == 'Total':
            # formatter = LogFormatter(10, labelOnlyBase=False)
            # pcolorOpts = {'norm':matplotlib.colors.SymLogNorm(linthresh=10, linscale=0.1)}

            u = total_field[src,'phi'] - phiScaleTotal

        elif Type == 'Primary':
            # formatter = LogFormatter(10, labelOnlyBase=False)
            # pcolorOpts = {'norm':matplotlib.colors.SymLogNorm(linthresh=10, linscale=0.1)}

            u = primary_field[src,'phi'] - phiScalePrim

        elif Type == 'Secondary':
            # formatter = None
            # pcolorOpts = {"cmap":"viridis"}

            uTotal = total_field[src,'phi'] - phiScaleTotal
            uPrim = primary_field[src,'phi'] - phiScalePrim
            u = uTotal - uPrim

    elif Field == 'E':

        label = 'Electric Field (V/m)'
        xtype = 'F'
        view = 'vec'
        streamOpts = {'color':'w'}
        ind = indF

        # formatter = LogFormatter(10, labelOnlyBase=False)
        # pcolorOpts = {'norm':matplotlib.colors.LogNorm()}
        formatter = "%.1e"
        pcolorOpts = {"cmap":"viridis"}

        if Type == 'Total':
            u = total_field[src,'e']

        elif Type == 'Primary':
            u = primary_field[src,'e']

        elif Type == 'Secondary':
            uTotal = total_field[src,'e']
            uPrim = primary_field[src,'e']
            u = uTotal - uPrim

    elif Field == 'J':

        label = 'Current density ($A/m^2$)'
        xtype = 'F'
        view = 'vec'
        streamOpts = {'color':'w'}
        ind = indF

        # formatter = LogFormatter(10, labelOnlyBase=False)
        # pcolorOpts = {'norm':matplotlib.colors.LogNorm()}
        formatter = "%.1e"
        pcolorOpts = {"cmap":"viridis"}

        if Type == 'Total':
            u = total_field[src,'j']

        elif Type == 'Primary':
            u = primary_field[src,'j']

        elif Type == 'Secondary':
            uTotal = total_field[src,'j']
            uPrim = primary_field[src,'j']
            u = uTotal - uPrim

    elif Field == 'Charge':

        label = 'Charge Density ($C/m^2$)'
        xtype = 'CC'
        view = 'real'
        streamOpts = None
        ind = indCC

        # formatter = LogFormatter(10, labelOnlyBase=False)
        # pcolorOpts = {'norm':matplotlib.colors.SymLogNorm(linthresh=1e-11, linscale=0.01)}
        formatter = "%.1e"
        pcolorOpts = {"cmap":"RdBu_r"}

        if Type == 'Total':
            u = total_field[src,'charge']

        elif Type == 'Primary':
            u = primary_field[src,'charge']

        elif Type == 'Secondary':
            uTotal = total_field[src,'charge']
            uPrim = primary_field[src,'charge']
            u = uTotal - uPrim

    elif Field == 'Sensitivity':

        label = 'Sensitivity'
        xtype = 'CC'
        view = 'real'
        streamOpts = None
        ind = indCC

        # formatter = None
        # pcolorOpts = {"cmap":"viridis"}
        # formatter = LogFormatter(10, labelOnlyBase=False)
        # pcolorOpts = {'norm':matplotlib.colors.SymLogNorm(linthresh=1e-2, linscale=0.01)}
        # formatter = formatter = "$10^{%.1f}$"
        formatter = "%.1e"
        pcolorOpts = {"cmap":"viridis"}

        if Type == 'Total':
            u = getSensitivity(survey,A,B,M,N,mtrue)

        elif Type == 'Primary':
            u = getSensitivity(survey,A,B,M,N,mhalf)

        elif Type == 'Secondary':
            uTotal = getSensitivity(survey,A,B,M,N,mtrue)
            uPrim = getSensitivity(survey,A,B,M,N,mhalf)
            u = uTotal - uPrim
        # u = np.log10(abs(u))

    dat = meshcore.plotImage(u[ind], vType = xtype, ax=ax[1], grid=False,view=view, streamOpts=streamOpts, pcolorOpts = pcolorOpts) #gridOpts={'color':'k', 'alpha':0.5}

    ax[1].set_xlabel('x (m)', fontsize= labelsize)
    ax[1].set_ylabel('z (m)', fontsize= labelsize)
    
    if(survey == "Dipole-Dipole"):
        ax[1].plot(A,1.,marker = 'v',color='red',markersize= labelsize)
        ax[1].plot(B,1.,marker = 'v',color='blue',markersize= labelsize)
        ax[1].plot(M,1.,marker = '^',color='yellow',markersize= labelsize)
        ax[1].plot(N,1.,marker = '^',color='green',markersize= labelsize)

        xytextA1 = (A-0.5,2.)
        xytextB1 = (B-0.5,2.)
        xytextM1 = (M-0.5,2.)
        xytextN1 = (N-0.5,2.)
        ax[1].annotate('A', xy=xytextA1, xytext=xytextA1,fontsize = labelsize)
        ax[1].annotate('B', xy=xytextB1, xytext=xytextB1,fontsize = labelsize)
        ax[1].annotate('M', xy=xytextM1, xytext=xytextM1,fontsize = labelsize)
        ax[1].annotate('N', xy=xytextN1, xytext=xytextN1,fontsize = labelsize)
    elif(survey == "Pole-Dipole"):
        ax[1].plot(A,1.,marker = 'v',color='red',markersize= labelsize)
        ax[1].plot(M,1.,marker = '^',color='yellow',markersize= labelsize)
        ax[1].plot(N,1.,marker = '^',color='green',markersize= labelsize)

        xytextA1 = (A-0.5,2.)
        xytextM1 = (M-0.5,2.)
        xytextN1 = (N-0.5,2.)
        ax[1].annotate('A', xy=xytextA1, xytext=xytextA1,fontsize = labelsize)
        ax[1].annotate('M', xy=xytextM1, xytext=xytextM1,fontsize = labelsize)
        ax[1].annotate('N', xy=xytextN1, xytext=xytextN1,fontsize = labelsize)
    elif(survey == "Dipole-Pole"):
        ax[1].plot(A,1.,marker = 'v',color='red',markersize= labelsize)
        ax[1].plot(B,1.,marker = 'v',color='blue',markersize= labelsize)
        ax[1].plot(M,1.,marker = '^',color='yellow',markersize= labelsize)

        xytextA1 = (A-0.5,2.)
        xytextB1 = (B-0.5,2.)
        xytextM1 = (M-0.5,2.)
        ax[1].annotate('A', xy=xytextA1, xytext=xytextA1,fontsize = labelsize)
        ax[1].annotate('B', xy=xytextB1, xytext=xytextB1,fontsize = labelsize)
        ax[1].annotate('M', xy=xytextM1, xytext=xytextM1,fontsize = labelsize)
    elif(survey == "Pole-Pole"):
        ax[1].plot(A,1.,marker = 'v',color='red',markersize= labelsize)
        ax[1].plot(M,1.,marker = '^',color='yellow',markersize= labelsize)

        xytextA1 = (A-0.5,2.)
        xytextM1 = (M-0.5,2.)
        ax[1].annotate('A', xy=xytextA1, xytext=xytextA1,fontsize = labelsize)
        ax[1].annotate('M', xy=xytextM1, xytext=xytextM1,fontsize = labelsize)

    ax[1].tick_params(axis='both', which='major', labelsize=ticksize)
    cbar_ax = fig.add_axes([0.8, 0.05, 0.08, 0.5])
    cbar_ax.axis('off')
    vmin, vmax = dat[0].get_clim()
    cb = plt.colorbar(dat[0], ax=cbar_ax,format = formatter, ticks = np.linspace(vmin, vmax, 5))
    #t_logloc = matplotlib.ticker.LogLocator(base=10.0, subs=[1.0,2.], numdecs=4, numticks=8)
    #tick_locator = matplotlib.ticker.SymmetricalLogLocator(t_logloc)
    #cb.locator = tick_locator
    #cb.ax.yaxis.set_major_locator(matplotlib.ticker.AutoLocator())
    #cb.update_ticks()
    cb.ax.tick_params(labelsize=ticksize)
    cb.set_label(label, fontsize=labelsize)
    ax[1].set_xlim([xmin,xmax])
    ax[1].set_ylim([ymin,ymax])
    ax[1].set_aspect('equal')

    # plt.show()
    # return fig, ax





def cylinder_app():
    app = interact(plot_Surface_Potentials,
            survey = ToggleButtons(options =['Dipole-Dipole','Dipole-Pole','Pole-Dipole','Pole-Pole'],value='Dipole-Dipole'),
            rhocyl = FloatText(min=1e-8,max=1e8, value = 500., continuous_update=False,description='$\\rho_2$'),
            rhohalf  = FloatText(min=1e-8,max=1e8, value = 500., continuous_update=False,description='$\\rho_1$'),
            r = FloatSlider(min=1.,max=20.,step=1.,value=10., continuous_update=False),
            xc = FloatSlider(min=-20.,max=20.,step=1.,value=0., continuous_update=False),
            yc = FloatSlider(min=-20.,max=0.,step=1.,value=-30., continuous_update=False),
            A = FloatSlider(min=-30.25,max=30.25,step=0.5,value=-30.25, continuous_update=False),
            B = FloatSlider(min=-30.25,max=30.25,step=0.5,value=30.25, continuous_update=False),
            M = FloatSlider(min=-30.25,max=30.25,step=0.5,value=-10.25, continuous_update=False),
            N = FloatSlider(min=-30.25,max=30.25,step=0.5,value=10.25, continuous_update=False),
            Field = ToggleButtons(options =['Model','Potential','E','J','Charge','Sensitivity'],value='Model'),
            Type = ToggleButtons(options =['Total','Primary','Secondary'],value='Total')
                )
    return app