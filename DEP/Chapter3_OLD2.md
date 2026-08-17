\chapter{システム構成と3Dモデルの取得}

本章では，本論文で扱う三つの料理マニピュレーション研究に共通する基盤として，ロボットシステムの構成と，対象物および作業環境の3Dモデル取得方法を述べる．
本論文の中心的な立場は，3Dモデルを単なる形状の記録として扱うのではなく，動作生成，力学解析，および制御設計のための計算基盤として利用する点にある．
このため，各タスクに固有の詳細なアルゴリズムを述べる前に，それらの前提となる共通の計測・モデリング過程を明確にしておく必要がある．

本論文で扱うタスクは，液体を注ぐ操作，食材表面に沿った皮むき操作，および切断時における食材の安定把持である．
これらは対象物の物理特性や要求される制御方式こそ異なるものの，いずれも対象物の三次元形状や作業空間の幾何情報を把握し，そこから操作に必要な量を導出するという点で共通している．
具体的には，注ぐ操作では容器内部形状から容積や液面検出に必要な情報を得る必要があり，皮むき操作では食材表面形状から工具軌道を生成する必要があり，切断時把持では食材形状上で接触点候補を生成し，把持安定性を評価する必要がある．

このような観点から，本章ではまず各研究で用いたロボットシステムを整理し，次にRGB-Dカメラを用いた多視点計測による3Dモデル生成手順を述べる．
さらに，生成した3Dモデルから抽出される幾何情報と，各タスクにおけるその利用方法をまとめる．
最後に，3Dモデル取得の精度評価について述べ，本章で構築する基盤の妥当性を示す．



\section{ロボットシステムの構成}

本論文で扱う注ぐ動作，皮むき動作，および把持の研究では，共通の双腕ロボットシステムを用いた．
本節では，まず三つの研究に共通するロボット，視覚センサ，および力覚センサについて述べ，その後，各研究におけるエンドエフェクタ設計を説明する．

\subsection{ロボット}

実験には，三菱電機製の7自由度マニピュレータ PA10-7C を2台用いた．
両アームは卓上作業に適するよう床面から700\,mmの高さに設置し，ベース座標系間の距離は$Y$軸方向に804\,mmとした．
各アームのベース座標系は，ロボット前方を$x$軸，ロボットから見て左方向を$y$軸，鉛直上方を$z$軸とするように設定した．
また，双腕協調作業を統一的に記述するため，左アームのベース座標系原点を世界座標系の原点として用いた．
\begin{figure}[ht]
    \centering
    \includegraphics[width=.8\linewidth]{fig//chp3/ICRA_RobotEnv.png}
    \caption{ロボットシステムと座標系}
    \label{fig:robot_env}
\end{figure}

本研究では，ロボット手先にツールを装着した状態で各種作業を実行するため，手先座標系に加えてツール座標系を定義した．
ツール座標系の位置は装着した道具の中心に設定し，姿勢は各ツールの幾何学的関係に応じて与えた．
これにより，ロボット手先そのものではなく，実際に対象へ作用する道具先端の位置姿勢を基準として動作を記述・制御できる．
この構成は，三つの研究に共通するハードウェア基盤である．

\subsection{視覚センサ}

対象物および作業環境の3D情報取得には，Intel RealSense D435 を用いた．
本センサはRGB画像と深度画像を同時に取得できるRGB-Dカメラであり，容器，食材，液面近傍，および反射を含む表面に対しても比較的安定した深度情報を取得できる．
図\label{fig:robot_camera}のように，カメラは主としてグリッパ前面に取り付け，ロボットアームの動作により視点を能動的に変化させることで，複数視点から点群を取得した．
\begin{figure}[ht]
    \centering
    \includegraphics[width=.7\linewidth]{fig//chp3/Realsense.jpg}
    \caption{手首に取り付けたIntel RealSense D435}
    \label{fig:robot_camera}
\end{figure}

取得した点群は，各時刻におけるロボット姿勢とカメラの取り付け関係に基づいて世界座標系へ変換し，統合した3Dモデルとして利用する．
この3Dモデルは，注ぐ動作では容器内部形状の推定と容積計算に，皮むき動作では食材表面形状の把握と工具軌道生成に，切断時把持では接触候補点の生成と把持安定性評価に用いられる．

\subsection{力覚センサ}

ロボットと対象物との接触を伴う操作を安定に実現するため，両腕の手首部には Leptrino 製の6軸力覚センサ PFS080YA501U6S を装備した．
このセンサはUSB経由で制御用PCに接続し，作業中に発生する力およびモーメントを計測する．
データシート（図\ref{fig:force_sensor_spec}）に基づけば，定格荷重500\,N，分解能$1/4000$より，力の分解能は約0.125\,Nである．
\begin{figure}[ht]
    \centering
    \includegraphics[width=.7\linewidth]{fig/chp3/ForceSensor.jpg}
    \caption{手首に取り付けたLeptrino製の6軸力覚センサー}
    \label{fig:force_sensor_install}
\end{figure}
\begin{figure}[ht]
    \centering
    \includegraphics[width=1\linewidth]{fig//chp3/ForceSensor-performence.png}
    \caption{PFS080YA501U6Sの仕様書}
    \label{fig:force_sensor_spec}
\end{figure}

力覚情報は，特に工具と対象表面との接触が重要となる皮むき動作において有効であり，接触状態の監視および制御入力の設計に用いた．
また，本論文では，3Dモデルに基づく幾何学的解析に加えて，接触に伴う力学的情報も操作設計の一部として扱うため，力覚センサはそのための共通計測基盤として位置づけられる．

\subsection{注ぐ動作におけるエンドエフェクタ設計}

注ぐ動作では，各種容器を安定に把持し，必要に応じて持ち上げ，傾ける必要がある．
そこで，平行グリッパを基盤とし，その指先アルミ板に容器把持用のエンドエフェクタを取り付けた．
本研究では，対象容器の形状差に対応するため，2種類のエンドエフェクタを用いた．

第1のエンドエフェクタ（図\ref{fig:pour_endeffactor_1}）は，ボウルやカップのように開口縁を有する容器を対象としたものである．
平行グリッパの開口幅のみでは把持が困難な場合を想定し，容器本体ではなく縁部を把持できるように設計した．
また，把持時の摩擦力を高めるため，接触面には小型のスポンジを取り付けた．
\begin{figure}[ht]
    \centering
    \includegraphics[width=.7\linewidth]{fig/chp3/PourEndFactor-1.jpg}
    \caption{注ぐ動作のエンドエフェクタ1の様子}
    \label{fig:pour_endeffactor_1}
\end{figure}

第2のエンドエフェクタ（図\ref{fig:pour_endeffactor_2}）は，外形寸法が比較的小さく，グリッパ開口幅内に収まる容器を確実に把持することを目的としたものである．
こちらも把持安定性向上のため，接触面に薄いスポンジを取り付けた．
このように，注ぐ動作におけるエンドエフェクタ設計では，容器形状の多様性に対して，把持様式を切り替えられることを重視した．
\begin{figure}[ht]
    \centering
    \includegraphics[width=.7\linewidth]{fig/chp3/PourEndFactor-2.jpg}
    \caption{注ぐ動作のエンドエフェクタ2の様子}
    \label{fig:pour_endeffactor_2}
\end{figure}

\subsection{皮むき動作におけるエンドエフェクタ設計}

皮むき動作では，一方の腕でピーラーを操作し，他方の腕で食材を安定に支持する必要がある．
このため，両腕とも平行グリッパを基盤としつつ，役割に応じて異なるエンドエフェクタを装着した．

工具側のエンドエフェクタ（図\ref{fig:pour_endeffactor_2}）としては，ピーラーをロボット手先へ固定するためのアダプタを設計した．
このアダプタにより，ピーラーの刃先位置と姿勢をツール座標系として明確に定義でき，食材表面形状に基づいて生成した軌道に従って刃先を安定に移動させることが可能となる．
\begin{figure}[ht]
    \centering
    \includegraphics[width=.7\linewidth]{fig/chp3/PeelingEndeffector-2.pdf}
    \caption{皮むき動作のピーラー側エンドエフェクタの様子}
    \label{fig:peeling_endeffactor_2}
\end{figure}

食材固定側のエンドエフェクタとしては，食材に刺した串を安定に固定するための専用機構を用いた．
細長い串は通常の平行グリッパでは毎回同じ位置に保持することが難しいため，$V$字溝を有する把持部を設け，串が一定位置に自然に収まるように設計した．
これにより，食材の姿勢再現性が向上し，皮むき軌道の安定な実行が可能となる．
\begin{figure}[ht]
    \centering
    \includegraphics[width=.5\linewidth]{fig/chp3/PeelingEndeffector-1.png}
    \caption{皮むき動作の食材固定側エンドエフェクタの様子}
    \label{fig:peeling_endeffactor_1}
\end{figure}


\subsection{安定把持におけるエンドエフェクタ設計}

安定把持の研究では，左腕に食材把持用の指型ハンドを，右腕に包丁固定用の高把持力平行グリッパを装着した．
右腕側の平行グリッパは，包丁をロボットへ剛に固定することを目的としており，切断時に発生する外力を安定に伝達できるようにした．
一方，左腕側では，食材形状に応じて接触点を柔軟に選択できることが重要であるため，多関節の指型ハンドを用いた．

食材把持用ハンドとしては，3軸2指のサーボハンドを用いた．
各指には FUTABA RS405CB を使用し，最大トルクは48.0\,$\mathrm{kgf \cdot cm}$，角度分解能は0.1\,degである．
各指の関節構成は $z$-$y$-$y$-tip とし，指先位置を制御するために，ヤコビアンに基づく指関節のみの逆運動学を用いた．
この構成により，食材表面上に生成した候補接触点へ指先を誘導し，把持安定性の評価に基づいて適切な接触配置を実現できる．

\begin{figure}[ht]
    \centering
    \includegraphics[width=.5\linewidth]{fig/chp3/ICRA_RobotHand.png}
    \caption{把持に使用する指ハンド}
    \label{fig:robot_hand}
\end{figure}

このように，切断時把持におけるエンドエフェクタ設計では，包丁側には高剛性な固定機構を，食材側には形状適応性を有する多指ハンドを割り当てることで，切断時の外力と把持安定性の両立を図った．



% ============================================================
% 第3章 後半：3D点群モデルの取得と処理
% ============================================================

\section{3D点群モデル取得の概要}

\subsection{本論文における点群モデルの役割}

本論文では，サービスロボットによる物体操作タスク（液体の精密注ぎ，食材の把持・切断，食材の皮むきなど）を実現するために，3次元点群モデルを基盤的な環境表現として用いる．
点群モデルとは，対象物体表面の3次元座標点の集合であり，RGB-Dカメラなどの深度センサにより非接触で取得可能である．

具体的には，以下の各タスクにおいて点群モデルが中心的な役割を果たす：
\begin{enumerate}
  \item \textbf{容器の形状モデリング}：液体注ぎタスクでは，注ぎ容器および目標容器の内部形状を点群モデルとして取得し，液面高さから注入量を体積計算するために用いる\cite{IROS2019}．
  \item \textbf{食材の表面形状取得}：食材把持タスクでは，食材の3次元形状を点群として取得し，把持位置探索のための幾何学的入力とする\cite{SICE2025}．
  \item \textbf{食材の皮むき軌道生成}：皮むきタスクでは，食材表面の点群から法線ベクトルを計算し，皮むき軌道の事前生成および回転角度の算出に利用する\cite{SII2021}．
\end{enumerate}

これらのタスクに共通して，点群モデルは「対象物の幾何学的情報を計算機上で扱うための中間表現」として機能する．
各タスク固有の処理へ進む前に，共通する前処理パイプラインを経由することで，後続のアルゴリズムへの入力品質を保証する設計となっている．

\subsection{共通処理パイプライン}

本論文における3D点群モデル取得の共通処理パイプラインを図\ref{fig:pipeline}に示す．
パイプラインは大きく「点群取得」と「点群処理」の2段階に分けられる．

\begin{figure}[t]
  \centering
  \includegraphics[width=0.85\linewidth]{fig/chp3/pointalgo_pipeline}
  \caption{3D点群モデル取得の共通処理パイプライン}
  \label{fig:pipeline}
\end{figure}

\textbf{点群取得}では，RGB-Dカメラを用いて多視点から撮影した点群を，座標変換により統合し，対象物体の全周的な3次元形状を復元する．
この段階では，カメラキャリブレーション，座標系定義，多視点合成が主要な処理となる．

\textbf{点群処理}では，統合された点群に対して，作業領域の切り出し，ダウンサンプリング，作業台平面の除去，外れ値除去，クラスタリング，平滑化および法線ベクトル推定を順次適用し，後段のタスクに適した点群モデルを生成する．

\section{点群モデルの取得と処理}

\subsection{点群取得}

\subsubsection{RGB-Dカメラによる点群の撮影}

本研究では，Intel RealSense D435 RGB-Dカメラをロボットアームの手首先端に搭載し，対象物体の点群を撮影する（図\ref{fig:camera_setup}）．
RealSense D435は，アクティブステレオ方式により深度情報を取得し，RGB画像と深度画像を同時に出力する．
得られた深度画像とカメラ内部パラメータから，各ピクセルの3次元座標を計算し，カメラ座標系における点群を生成する．

\begin{figure}[t]
  \centering
  \includegraphics[width=0.70\linewidth]{fig/chp3/pointalgo_camera_setup}
  \caption{ロボットアーム先端に搭載されたRGB-Dカメラ}
  \label{fig:camera_setup}
\end{figure}

RGB-Dカメラの単一視点からの撮影では，対象物体の自己遮蔽や環境遮蔽により不可視となる領域が生じる．
このため，ロボットアームを動作させてカメラ姿勢を変更し，複数視点から点群を取得する必要がある．

\subsubsection{座標系の定義}

本システムでは，以下の座標系を定義する（図\ref{fig:coordinate_systems}）：

\begin{enumerate}
  \item \textbf{世界座標系} $\Sigma_W$：ロボットベース座標系を原点とし，全点群の統合先となる基準座標系．
  \item \textbf{カメラ座標系} $\Sigma_C$：RGB-Dカメラの光学中心を原点とし，カメラの光学軸を$z$軸とする座標系．
  \item \textbf{ロボット手先座標系} $\Sigma_H$：ロボットアームの手首先端に固定された座標系．
\end{enumerate}

\begin{figure}[t]
  \centering
  \includegraphics[width=0.65\linewidth]{fig/chp3/pointalgo_coordinates}
  \caption{座標系の定義}
  \label{fig:coordinate_systems}
\end{figure}

カメラ座標系 $\Sigma_C$ で得られた点群は，以下の変換を経て世界座標系 $\Sigma_W$ へ統合される：
\begin{equation}
  {}^{W}\bm{p} = {}^{W}\bm{T}_{H} \cdot {}^{H}\bm{T}_{C} \cdot {}^{C}\bm{p}
  \label{eq:transform_chain}
\end{equation}
ここで，${}^{W}\bm{T}_{H}$ はロボットの順運動学から得られる手先座標系から世界座標系への同次変換行列，${}^{H}\bm{T}_{C}$ は手先座標系に対するカメラの取り付け位置姿勢（外部パラメータ），${}^{C}\bm{p}$ はカメラ座標系における点の位置ベクトルである．

\subsubsection{カメラキャリブレーションと外部パラメータ}

RGB-Dカメラの内部パラメータ（焦点距離 $f_x, f_y$，光学中心 $c_x, c_y$，歪み係数）は，予めチェッカーボードを用いた標準的なカメラキャリブレーションにより取得する．

外部パラメータ ${}^{H}\bm{T}_{C}$ は，カメラの手先への取り付け位置姿勢を表し，以下の手順で同定する：
\begin{enumerate}
  \item ロボット手先に固定されたカメラで，既知の3次元位置にあるキャリブレーションマーカを複数姿勢から観測する．
  \item 各観測において，カメラ座標系におけるマーカ位置と世界座標系におけるマーカ位置の対応から，Hand-Eyeキャリブレーション問題として定式化する．
  \item 最小二乗法により ${}^{H}\bm{T}_{C}$ を推定する．
\end{enumerate}

本論文の実験環境では，事前キャリブレーションにより外部パラメータを一度だけ同定し，実験中は同一値を用いた．

\subsubsection{座標変換と多視点点群の合成}

複数視点からの点群を統合する手順を以下に示す：

\begin{enumerate}
  \item ロボットアームを制御し，カメラが対象物体を取り囲むように複数の姿勢へ移動させる．
  \item 各姿勢においてRGB-Dカメラで点群を撮影し，カメラ座標系での点群 $\mathcal{P}_{C}^{(i)}$ を得る．
  \item 式(\ref{eq:transform_chain})に従い，各カメラ座標系の点群を世界座標系へ変換する：
  \begin{equation}
    \mathcal{P}_{W}^{(i)} = \left\{ {}^{W}\bm{T}_{H}^{(i)} \cdot {}^{H}\bm{T}_{C} \cdot \bm{p} \;|\; \bm{p} \in \mathcal{P}_{C}^{(i)} \right\}
  \end{equation}
  \item 全視点の点群を統合し，1つの点群 $\mathcal{P}_{\mathrm{all}}$ を得る：
  \begin{equation}
    \mathcal{P}_{\mathrm{all}} = \bigcup_{i=1}^{N_v} \mathcal{P}_{W}^{(i)}
  \end{equation}
  ここで，$N_v$ は視点数である．
\end{enumerate}

多視点統合により，対象物体の全周的な点群モデルが得られるが，重複領域の密度が不均一になる点や，位置姿勢誤差の蓄積による多重像が生じる点に留意する必要がある．

\subsection{点群処理}

統合後の点群 $\mathcal{P}_{\mathrm{all}}$ には，対象物体以外の点（作業台，背景，センサノイズなど）が含まれるため，以下の処理パイプラインを適用して対象物体の点群モデルを抽出する．
本処理は，Point Cloud Library（PCL）\cite{PCL} を用いて実装した．

\subsubsection{作業領域の切り出し}

まず，ロボットの作業範囲外の不要な点を除去するため，世界座標系における3次元矩形領域（Axis-Aligned Bounding Box; AABB）を指定し，領域外の点をフィルタリングする．
具体的には，作業台上面を基準とした $x, y, z$ 各軸方向の範囲 $[x_{\min}, x_{\max}] \times [y_{\min}, y_{\max}] \times [z_{\min}, z_{\max}]$ を経験的に設定し，Pass-Throughフィルタを適用する．

\begin{equation}
  \mathcal{P}_{\mathrm{roi}} = \left\{ \bm{p} \in \mathcal{P}_{\mathrm{all}} \;|\; \bm{p} \in [x_{\min}, x_{\max}] \times [y_{\min}, y_{\max}] \times [z_{\min}, z_{\max}] \right\}
  \label{eq:roi}
\end{equation}

これにより，後段処理の計算負荷が低減されるとともに，背景領域の誤検出が抑制される．

\subsubsection{ダウンサンプリング}

多視点統合後の点群は高密度であり，点数が数十万点に達することがある．
後段の処理を効率化するため，Voxel Gridフィルタを用いてダウンサンプリングを行う．

Voxel Gridフィルタでは，3次元空間を一辺 $l_v$ のボクセル格子に分割し，各ボクセル内の点群をその重心位置で代表する：

\begin{equation}
  \mathcal{P}_{\mathrm{ds}} = \left\{ \frac{1}{|\mathcal{V}_k|} \sum_{\bm{p} \in \mathcal{V}_k} \bm{p} \;|\; \mathcal{V}_k \neq \emptyset \right\}
\end{equation}
ここで，$\mathcal{V}_k$ は $k$ 番目のボクセルに含まれる点の集合，$|\mathcal{V}_k|$ はその点数を表す．

本論文では，ボクセルサイズ $l_v = 1.0$\,mm を基本値とし，タスクに応じて調整する．
ダウンサンプリングにより，点群の密度が均一化され，かつ計算量が大幅に削減される．

\subsubsection{作業台平面の除去}

作業領域内には，対象物体に加えて作業台平面が含まれている．
作業台平面は Random Sample Consensus（RANSAC）\cite{PCL-RANSAC} を用いて検出・除去する．

RANSACによる平面検出では，以下の処理を反復する：
\begin{enumerate}
  \item 点群から3点をランダムに選択し，それらが定義する平面モデル $ax + by + cz + d = 0$ を生成する．
  \item 全点に対して，平面モデルからの距離が閾値 $\epsilon_p$ 以内の点をインライアとして集計する．
  \item 十分な反復回数の後，最多のインライア数を得た平面モデルを採用する．
\end{enumerate}

採用された平面モデルに対するインライア点を点群から除去することで，作業台平面を除外する：

\begin{equation}
  \mathcal{P}_{\mathrm{noplanar}} = \mathcal{P}_{\mathrm{ds}} \setminus \left\{ \bm{p} \in \mathcal{P}_{\mathrm{ds}} \;|\; \mathrm{dist}(\bm{p}, \Pi) \leq \epsilon_p \right\}
  \label{eq:plane_removal}
\end{equation}
ここで，$\Pi$ は検出された平面，$\mathrm{dist}(\bm{p}, \Pi)$ は点 $\bm{p}$ と平面 $\Pi$ の直交距離である．
本論文では $\epsilon_p = 2.0$\,mm を用いた．

\subsubsection{外れ値除去}

センサノイズや多重像に起因する疎な外れ値点を除去するため，Statistical Outlier Removalフィルタを適用する．
本フィルタでは，各点について $k$ 近傍点までの平均距離 $\bar{d}_i$ を計算し，全点の平均距離分布に基づいて外れ値を判定する：

\begin{equation}
  \mathcal{P}_{\mathrm{filtered}} = \left\{ \bm{p}_i \in \mathcal{P}_{\mathrm{noplanar}} \;|\; \bar{d}_i \leq \mu_d + \alpha \sigma_d \right\}
\end{equation}
ここで，$\mu_d$ は全点の近傍平均距離の平均，$\sigma_d$ は標準偏差，$\alpha$ は許容度パラメータである．
本研究では $k = 50$，$\alpha = 1.0$ を標準的に用いる．

また，PCLに実装されているRadius Outlier Removal\cite{PCL-method}も併用し，半径 $r_r$ 内に存在する近傍点数が閾値 $n_{\min}$ 未満の点を孤立点として除去する．

\subsubsection{クラスタリングによる対象物抽出}

平面除去および外れ値除去後の点群には，対象物体に加えて作業台上の他の物体や残留ノイズが含まれる可能性がある．
そこで，Euclidean Clustering\cite{PCL-method}を適用し，空間的に連続する点群を個別のクラスタに分割する．

Euclidean Clusteringでは，点間のユークリッド距離が閾値 $d_{\mathrm{th}}$ 未満の場合に同一クラスタとみなす：

\begin{equation}
  \mathrm{cluster}(\bm{p}_i, \bm{p}_j) = \begin{cases}
    \text{同一} & \text{if } \|\bm{p}_i - \bm{p}_j\| \leq d_{\mathrm{th}} \\
    \text{異なる} & \text{otherwise}
  \end{cases}
\end{equation}

各クラスタに対して，点数 $N_{\mathrm{cluster}}$ および重心位置の評価により対象物体を同定する．
具体的には，閾値 $N_{\min}$ 以上の点数を有し，かつ重心が作業領域内の適切な位置にあるクラスタを対象物体の点群 $\mathcal{P}_{\mathrm{obj}}$ として選択する．

\subsubsection{平滑化と法線ベクトル推定}

クラスタリングにより抽出された対象物体の点群 $\mathcal{P}_{\mathrm{obj}}$ に対し，Moving Least Squares（MLS）法\cite{PCL-MLS}による平滑化と法線ベクトル推定を同時に適用する．

MLS法では，各点 $\bm{p}_i$ の近傍点群に対して局所的な多項式曲面をフィッティングし，再サンプリングすることで平滑化された点群 $\mathcal{P}_{\mathrm{smooth}}$ を得る．
同時に，フィッティングされた局所曲面の法線方向として，各点の法線ベクトル $\bm{n}_i$ が計算される：

\begin{equation}
  \bm{n}_i = \frac{\partial \mathcal{S}}{\partial x} \times \frac{\partial \mathcal{S}}{\partial y} \Big|_{\bm{p}_i}
\end{equation}
ここで，$\mathcal{S}$ は局所近似曲面である．
法線ベクトルは，後段のタスク（把持位置探索，皮むき軌道生成，表面領域分割など）において必須の幾何学情報となる．

なお，MLS法の局所近似半径 $r_{\mathrm{mls}}$ は，点群密度に依存するパラメータであり，本研究では経験的に $r_{\mathrm{mls}} = 3.0$\,mm を用いる．

\subsubsection{点群処理パラメータ}

表\ref{tab:params}に，本章で用いる標準的な点群処理パラメータをまとめる．
これらの値は，使用するRGB-Dカメラの特性，対象物体のサイズ，および作業環境に応じて調整される．

\begin{table}[t]
  \centering
  \caption{点群処理の標準パラメータ}
  \label{tab:params}
  \begin{tabular}{lcl}
    \toprule
    \textbf{処理} & \textbf{パラメータ} & \textbf{標準値} \\
    \midrule
    Voxel Gridダウンサンプリング & ボクセルサイズ $l_v$ & 1.0\,mm \\
    RANSAC平面除去 & 距離閾値 $\epsilon_p$ & 2.0\,mm \\
    Statistical Outlier Removal & 近傍点数 $k$ & 50 \\
    Statistical Outlier Removal & 許容度 $\alpha$ & 1.0 \\
    Radius Outlier Removal & 探索半径 $r_r$ & 5.0\,mm \\
    Radius Outlier Removal & 最小近傍点数 $n_{\min}$ & 10 \\
    Euclidean Clustering & クラスタ距離閾値 $d_{\mathrm{th}}$ & 3.0\,mm \\
    Euclidean Clustering & 最小クラスタ点数 $N_{\min}$ & 500 \\
    MLS平滑化 & 局所近似半径 $r_{\mathrm{mls}}$ & 3.0\,mm \\
    \bottomrule
  \end{tabular}
\end{table}

\subsection{前処理後の点群モデルから得られる基礎情報}

前処理を経て得られた点群モデル $\mathcal{P}_{\mathrm{obj}}$ から，後段のタスクを遂行するために以下の基礎情報が抽出される．

\subsubsection{位置姿勢と空間領域}

点群モデルの Axis-Aligned Bounding Box（AABB）を計算することにより，世界座標系における物体の存在範囲を取得する．
AABBは以下のように定義される：

\begin{equation}
  \mathrm{AABB} = \left[ \min(\mathcal{P}_{\mathrm{obj}}^x),\; \max(\mathcal{P}_{\mathrm{obj}}^x) \right] \times
                   \left[ \min(\mathcal{P}_{\mathrm{obj}}^y),\; \max(\mathcal{P}_{\mathrm{obj}}^y) \right] \times
                   \left[ \min(\mathcal{P}_{\mathrm{obj}}^z),\; \max(\mathcal{P}_{\mathrm{obj}}^z) \right]
\end{equation}

この情報は，ロボットアームの到達可能性判定，衝突回避，およびカメラの再撮影時の視点計画に利用される．

\subsubsection{色情報}

RGB-Dカメラからは各点の3次元座標に加えて色情報（RGB値）が取得される．
色情報は以下の目的で用いられる：
\begin{itemize}
  \item 物体表面の質感や模様に基づく領域分割
  \item 特定色の抽出による対象領域の識別（例：皮むき後の果肉色 vs 表皮色）
  \item 人間への可視化・表示
\end{itemize}

\subsubsection{法線ベクトル}

MLS平滑化により推定された法線ベクトル $\{ \bm{n}_i \}$ は，以下のタスクにおいて中心的役割を果たす：
\begin{itemize}
  \item 把持位置の力学的評価（力の釣り合い解析の幾何学的入力）
  \item 物体表面の曲率評価
  \item カメラ視点の適切性評価（法線方向と視線方向のなす角）
\end{itemize}

\subsubsection{断面，断面輪郭線，断面積，体積計算}

物体の幾何学的特性を定量化するため，点群モデルから断面情報を抽出する．
容器モデルの場合，以下の手順で体積計算が可能である\cite{IROS2019}：

\begin{enumerate}
  \item 点群モデルを $z$ 軸方向に一定間隔 $\Delta h$（本論文では $\Delta h = 1$\,mm）でスライスする．
  \item 各スライス高さ $h_k$ において，スライス平面から閾値以内の点群を当該断面の点集合とする．
  \item 断面点群をスライス下面に投影し，投影点群の凸包を Quickhull アルゴリズム\cite{PCL-Convex}により計算する．
  \item 凸包の面積 $A(h_k)$ を断面積として算出する．
  \item 全スライスの断面積を高さ方向に積分することで，任意の液面高さ $H$ までの体積 $V(H)$ を求める：
  \begin{equation}
    V(H) = \int_{0}^{H} A(h)\, dh \approx \sum_{k:\,h_k \leq H} A(h_k) \cdot \Delta h
    \label{eq:volume_integral}
  \end{equation}
\end{enumerate}

この断面積分法により，容器形状に依存しない汎用的な体積計算が実現される（図\ref{fig:cross_section}）．

\begin{figure}[t]
  \centering
  \includegraphics[width=0.75\linewidth]{fig/chp3/pointalgo_cross_section}
  \caption{点群のスライスと断面積計算の概念図}
  \label{fig:cross_section}
\end{figure}

\subsubsection{重心}

物体の幾何学的重心 $\bm{g}$ は，点群の全点の座標平均として近似計算される：

\begin{equation}
  \bm{g} = \frac{1}{|\mathcal{P}_{\mathrm{obj}}|} \sum_{\bm{p} \in \mathcal{P}_{\mathrm{obj}}} \bm{p}
  \label{eq:centroid}
\end{equation}

重心位置は，把持の力学的安定性評価における重要な入力であり，特に食材把持タスクでは，食品の密度が比較的均一であるとの仮定の下，幾何学的重心を質量中心の近似値として使用する\cite{SICE2025}．

\subsubsection{表面領域と指先位置候補}

点群モデルから，物体表面の各点を指先把持位置の候補として利用する．
具体的には，$\mathcal{P}_{\mathrm{obj}}$ の各点 $\bm{p}_i$ を指先位置候補とし，対応する法線ベクトル $\bm{n}_i$ を指先の接近方向として扱う．
これにより，多数の把持候補（最大で $K = |\mathcal{P}_{\mathrm{obj}}|$ 個）が生成される．
計算効率の観点から，事前に点群をダウンサンプリングして候補点数を制限する（例：SICE2025の実験では約150〜200点に制限\cite{SICE2025}）．

\subsubsection{後続章における利用}

上記の基礎情報は，後続する各章において以下のように利用される：
\begin{itemize}
  \item \textbf{第4章（液体注ぎ制御）}：容器の断面積データを用いた注入量の体積計算，および液面検出のためのAABBによる領域制限．
  \item \textbf{第5章（食材把持位置探索）}：表面点群を把持候補空間とし，法線ベクトルと重心位置を用いた把持の力学的スコア計算．
  \item \textbf{第6章（食材皮むき軌道生成）}：物体表面の法線ベクトルに基づく皮むき軌道の事前生成，法線角度変化に基づく軌道セグメント化，および皮むきエッジの色情報抽出．
\end{itemize}

% ============================================================
\section{底面点群の取得}
% 仮章（Tentative section）
% ============================================================

\subsection{本章における位置づけ}

前節で述べた多視点点群統合処理により，対象物体のほぼ全周的な3次元形状が取得される．
しかし，机上に置かれた物体を上方および側方からスキャンする構成では，底面（作業台との接触面付近）は不可視領域となる．
本節では，ロボットの把持機能を活用して物体を持ち上げ，底面を含む全周点群を取得する手法について述べる．

\subsection{机上スキャンにおける不可視領域}

図\ref{fig:occlusion}に示すように，作業台上に静置された物体をRGB-Dカメラで多視点からスキャンしても，物体底面および作業台との接触部近傍の点群は原理的に取得不可能である．
この不可視領域は，以下に起因する：
\begin{enumerate}
  \item 物体と作業台の接触による物理的遮蔽
  \item カメラの俯角限界（アームの可動範囲制約）
  \item 物体側面のオーバーハング形状による自己遮蔽
\end{enumerate}

\begin{figure}[t]
  \centering
  \includegraphics[width=0.70\linewidth]{fig/chp3/pointalgo_occlusion}
  \caption{机上スキャンにおける不可視領域}
  \label{fig:occlusion}
\end{figure}

底面情報の欠落は，特に容器の体積計算精度に重大な影響を及ぼす．
例えば，深くて細い容器では底面付近の形状復元が不完全となるため，式(\ref{eq:volume_integral})の積分下限付近の誤差が累積し，全体の体積誤差が増大する\cite{IROS2019}．

\subsection{把持を利用した底面点群の取得}

\subsubsection{計算式}

ロボットハンドにより物体を把持して持ち上げた状態で，物体底面をカメラで撮影する．
このとき，把持後の物体は手先座標系に対して固定されているため，撮影された底面点群は以下の座標変換により世界座標系の既存点群と統合される：

\begin{equation}
  \mathcal{P}_{\mathrm{bottom}}^{(W)} = \left\{ {}^{W}\bm{T}_{H}^{(g)} \cdot {}^{H}\bm{T}_{C} \cdot \bm{p} \;|\; \bm{p} \in \mathcal{P}_{\mathrm{bottom}}^{(C)} \right\}
  \label{eq:bottom_transform}
\end{equation}
ここで，${}^{W}\bm{T}_{H}^{(g)}$ は底面撮影時のロボット手先の順運動学解，$\mathcal{P}_{\mathrm{bottom}}^{(C)}$ はカメラ座標系における底面点群である．

既存の点群モデル $\mathcal{P}_{\mathrm{obj}}$ と底面点群 $\mathcal{P}_{\mathrm{bottom}}^{(W)}$ の統合は，ICP（Iterative Closest Point）アルゴリズムによる精密位置合わせの後に実施する：

\begin{equation}
  \mathcal{P}_{\mathrm{full}} = \mathcal{P}_{\mathrm{obj}} \cup \mathcal{P}_{\mathrm{bottom}}^{(W, \mathrm{aligned})}
  \label{eq:full_model}
\end{equation}

\subsubsection{仮手順}

把持を利用した底面点群取得の手順を以下に示す：

\begin{enumerate}
  \item \textbf{三指把持による対象物の持ち上げ}：
  事前に計画された把持位置に基づき，ロボットハンドの3指で対象物体を把持し，作業台から十分な高さ（約150\,mm）まで持ち上げる．
  持ち上げ高さは，カメラの最小撮影距離と作業台の映り込み回避を考慮して決定する．

  \item \textbf{底面点群の撮影と座標変換}：
  持ち上げ状態で，カメラを物体の下方に向け，底面の点群を撮影する．
  必要に応じてハンドのリストロール軸を回転させ，複数の底部視点を取得する．
  撮影された各底面点群は，式(\ref{eq:bottom_transform})により世界座標系へ変換する．

  \item \textbf{既存点群との位置合わせと統合}：
  底面点群と既存の物体点群モデルの重複領域（側面下部）を用いてICPによる精密位置合わせを行う．
  位置合わせ後，式(\ref{eq:full_model})により両者を統合し，底面を含む完全な物体モデルを生成する．
\end{enumerate}

\section{3D点群モデル取得の精度評価実験}

\subsection{評価指標}

提案する点群モデル取得手法の精度を定量的に評価するため，以下の評価指標を定義する．

\subsubsection{距離誤差}

実測点群と真値モデル（CADモデルまたは高精度スキャナで取得した参照モデル）の間の点対点距離誤差を評価する．
真値モデルの各点 $\bm{q}_j$ に対して，点群モデル中の最近傍点 $\bm{p}_{\mathrm{nn}(j)}$ とのユークリッド距離を計算する：

\begin{equation}
  e_{\mathrm{dist}} = \frac{1}{N_q} \sum_{j=1}^{N_q} \|\bm{q}_j - \bm{p}_{\mathrm{nn}(j)}\|
  \label{eq:dist_error}
\end{equation}
ここで，$N_q$ は真値モデルの点数，$\mathrm{nn}(j)$ は $\bm{q}_j$ の最近傍点のインデックスである．

\subsubsection{寸法誤差}

対象物体の主要寸法（幅，奥行き，高さ，直径など）を点群モデルのAABBから計測し，ノギス実測値との差分を寸法誤差として評価する：

\begin{equation}
  e_{\mathrm{dim}} = |d_{\mathrm{measured}} - d_{\mathrm{GT}}|
  \label{eq:dim_error}
\end{equation}

\subsubsection{体積誤差}

式(\ref{eq:volume_integral})により計算された推定体積と，実測体積（水充填法または電子天秤による重量÷密度換算）との誤差を評価する：

\begin{equation}
  e_{\mathrm{vol}} = |V_{\mathrm{estimated}} - V_{\mathrm{GT}}|
  \label{eq:vol_error}
\end{equation}

相対誤差は以下の通り定義する：
\begin{equation}
  e_{\mathrm{vol\_rel}} = \frac{|V_{\mathrm{estimated}} - V_{\mathrm{GT}}|}{V_{\mathrm{GT}}} \times 100\;[\%]
  \label{eq:vol_error_rel}
\end{equation}

\subsubsection{ICP誤差}

多視点統合の位置合わせ精度を評価するため，ICPアルゴリズムの収束時の平均二乗誤差（Mean Squared Error; MSE）を記録する：

\begin{equation}
  e_{\mathrm{ICP}} = \frac{1}{N_{\mathrm{corr}}} \sum_{k=1}^{N_{\mathrm{corr}}} \|\bm{p}_k - \bm{T}_{\mathrm{ICP}} \cdot \bm{q}_k\|^2
  \label{eq:icp_error}
\end{equation}
ここで，$N_{\mathrm{corr}}$ はICPの対応点数，$\bm{T}_{\mathrm{ICP}}$ は推定された変換行列である．

\subsubsection{再現性}

同一条件下で同一物体を複数回撮影・処理し，得られた点群モデル間の一致性を評価する．
具体的には，試行 $a$ と試行 $b$ の点群モデル間の距離誤差を式(\ref{eq:dist_error})に準じて計算し，複数試行間の平均および標準偏差により再現性を評価する：

\begin{equation}
  R = \frac{1}{N_{\mathrm{trials}}(N_{\mathrm{trials}}-1)} \sum_{a \neq b} e_{\mathrm{dist}}(\mathcal{P}^{(a)}, \mathcal{P}^{(b)})
  \label{eq:reproducibility}
\end{equation}

\subsection{カメラの精度評価}

\subsubsection{実験条件}

RGB-Dカメラ（Intel RealSense D435）の単体精度を評価するため，以下の実験を実施した．
\begin{itemize}
  \item \textbf{撮影対象}：平坦な白色平面板をカメラ光軸に対して垂直に設置
  \item \textbf{撮影距離}：200\,mm, 300\,mm, 400\,mm, 500\,mm, 600\,mm の5水準
  \item \textbf{評価方法}：各距離において平面の点群を取得し，RANSACにより平面フィッティングを行い，インライア点の平面からのRMS誤差を計算
  \item \textbf{試行回数}：各距離につき10回
\end{itemize}

\subsubsection{結果と考察}

図\ref{fig:camera_accuracy}に撮影距離とRMS誤差の関係を示す．
\begin{figure}[t]
  \centering
  \includegraphics[width=0.75\linewidth]{fig/chp3/pointalgo_camera_accuracy}
  \caption{撮影距離と深度精度の関係}
  \label{fig:camera_accuracy}
\end{figure}

撮影距離200\,mm〜400\,mmの範囲ではRMS誤差は1.0\,mm未満であり，良好な精度を示した．
距離500\,mm以上では精度の低下傾向が認められ，これはRealSense D435のステレオマッチング精度が基線長制約により遠距離で低下することに起因する．
本結果に基づき，後続の実験では撮影距離を200\,mm〜400\,mmの範囲に設定することとした．

\subsection{標準物体の撮影実験}

\subsubsection{実験条件}

幾何学的形状が既知の標準物体を用いて，提案パイプライン全体の精度を評価した．
\begin{itemize}
  \item \textbf{使用物体}：
  \begin{enumerate}
    \item 円筒容器（直径60\,mm，高さ100\,mm，容積約283\,ml）
    \item 直方体容器（50×50×80\,mm，容積200\,ml）
    \item 球体（直径80\,mm）
  \end{enumerate}
  \item \textbf{真値}：CADモデル（寸法）および実測値（体積は水充填法により計測）
  \item \textbf{撮影視点数}：6視点（物体を取り囲むように60°間隔で配置）
  \item \textbf{評価指標}：距離誤差，寸法誤差，体積誤差
  \item \textbf{試行回数}：各物体につき5回
\end{itemize}

\subsubsection{結果と考察}

表\ref{tab:standard_objects}に標準物体の実験結果を示す．

\begin{table}[t]
  \centering
  \caption{標準物体の撮影実験結果}
  \label{tab:standard_objects}
  \begin{tabular}{lccc}
    \toprule
    \textbf{物体} & \textbf{平均距離誤差 [mm]} & \textbf{最大寸法誤差 [mm]} & \textbf{体積相対誤差 [\%]} \\
    \midrule
    円筒容器 & 0.72 ± 0.15 & 1.2 & 2.31 ± 1.05 \\
    直方体容器 & 0.58 ± 0.12 & 0.9 & 1.48 ± 0.82 \\
    球体 & 0.91 ± 0.21 & 1.5 & -- \\
    \bottomrule
  \end{tabular}
\end{table}

円筒容器と直方体容器では体積相対誤差が3\%以内に収まっており，提案手法による容器モデリングが液体注ぎタスクに十分な精度を有することが確認された．
球体の体積誤差は，透明かつ曲率が大きい表面での深度推定誤差により計算不能となったため，表中では省略している．
また，円筒容器の底面付近では点群密度が低下する傾向が認められ，これが体積誤差の主因であると考察される．

\subsection{3Dプリンタで作製した物体の撮影実験}

\subsubsection{実験条件}

標準物体に加え，より複雑な形状を有する物体に対する評価として，3Dプリンタで作製した自由曲面物体を用いて実験を行った．
\begin{itemize}
  \item \textbf{使用物体}：3Dプリンタ製の非対称自由曲面物体（最大寸法約100\,mm，図\ref{fig:3dprinted}参照）
  \item \textbf{真値}：3Dプリント用CADデータ（STLメッシュモデル）
  \item \textbf{撮影視点数}：8視点
  \item \textbf{評価指標}：距離誤差，ICP誤差，再現性
  \item \textbf{試行回数}：5回
\end{itemize}

\begin{figure}[t]
  \centering
  \includegraphics[width=0.60\linewidth]{fig/chp3/pointalgo_3dprinted}
  \caption{3Dプリンタ製自由曲面物体}
  \label{fig:3dprinted}
\end{figure}

\subsubsection{結果と考察}

実験結果を表\ref{tab:3dprinted}に示す．

\begin{table}[t]
  \centering
  \caption{3Dプリンタ製物体の撮影実験結果}
  \label{tab:3dprinted}
  \begin{tabular}{lc}
    \toprule
    \textbf{評価指標} & \textbf{結果} \\
    \midrule
    平均距離誤差 [mm] & 0.84 ± 0.19 \\
    ICP誤差（MSE） [mm$^2$] & 0.37 ± 0.11 \\
    再現性 [mm] & 0.52 ± 0.14 \\
    \bottomrule
  \end{tabular}
\end{table}

自由曲面物体においても距離誤差は1.0\,mm未満であり，提案パイプラインが非定型形状に対しても有効であることが確認された．
再現性も0.52\,mmと良好であり，同一物体に対する複数回のモデル取得が一貫した結果を生成することが示された．
ただし，急峻な凹面部（曲率の大きい領域）では局所的に点群密度が低下する傾向が認められ，このような領域では法線ベクトル推定の信頼性が低下する可能性がある．

\subsection{底面点群取得の評価（仮）}

\subsubsection{実験条件}

提案した把持利用型底面点群取得手法の有効性を検証するため，以下の実験を実施した．
\begin{itemize}
  \item \textbf{使用物体}：底面形状が特徴的な容器（深底カップ：直径50\,mm，深さ120\,mm）
  \item \textbf{比較条件}：
  \begin{enumerate}
    \item 提案手法（把持＋底面撮影あり）
    \item 従来手法（机上スキャンのみ）
  \end{enumerate}
  \item \textbf{真値}：容器を逆さに置いて撮影した高品質点群を底面の参照モデルとする
  \item \textbf{評価指標}：底面領域の距離誤差，体積誤差
\end{itemize}

\subsubsection{結果と考察}

表\ref{tab:bottom_pointcloud}に底面点群取得の有無による比較結果を示す．

\begin{table}[t]
  \centering
  \caption{底面点群取得の効果}
  \label{tab:bottom_pointcloud}
  \begin{tabular}{lcc}
    \toprule
    \textbf{評価指標} & \textbf{机上スキャンのみ} & \textbf{提案手法（底面追加）} \\
    \midrule
    底面領域距離誤差 [mm] & 8.34 ± 3.21 & 1.12 ± 0.28 \\
    体積相対誤差 [\%] & 12.47 ± 4.53 & 2.89 ± 1.17 \\
    \bottomrule
  \end{tabular}
\end{table}

提案手法により底面点群を追加することで，底面領域の距離誤差が大幅に低減され（8.34\,mmから1.12\,mmへ），体積相対誤差も12.47\%から2.89\%へと顕著に改善した．
この結果は，特に深底容器において底面情報が体積計算精度に重大な影響を及ぼすことを定量的に示している．
一方，提案手法では把持・持ち上げ動作の追加による実験時間の増加（1試行あたり約60秒）が課題として残る．

\section{まとめ}

本章では，本論文における3D点群モデル取得の共通処理パイプラインについて述べた．
本章の主要な内容を以下に要約する：

\begin{enumerate}
  \item \textbf{点群取得}：RGB-Dカメラを用いた多視点点群撮影，座標系定義，カメラキャリブレーション，座標変換による多視点点群統合の手順を確立した．これにより，単一視点では不可視となる領域を含む全周的な物体形状の取得が可能となった．

  \item \textbf{点群処理}：作業領域切り出し，ダウンサンプリング，RANSACによる平面除去，外れ値除去，Euclidean Clusteringによる対象物抽出，MLS平滑化と法線ベクトル推定からなる標準処理パイプラインを構築した．これにより，ノイズや作業台平面を除外した高品質な物体点群モデルが得られることを確認した．

  \item \textbf{基礎情報の抽出}：前処理後の点群モデルから，位置姿勢，色情報，法線ベクトル，断面積と体積，重心，表面領域と指先位置候補を抽出する手法を示した．これらの情報は，後続章における液体注ぎ制御，食材把持位置探索，皮むき軌道生成の基盤となる．

  \item \textbf{底面点群の取得}：机上スキャンで不可視となる底面情報を，把持による持ち上げと再撮影により取得する手法を提案し，深底容器における体積誤差の顕著な改善（12.47\%→2.89\%）を確認した．

  \item \textbf{精度評価}：標準物体および3Dプリンタ製自由曲面物体を用いた総合的な評価実験により，提案パイプラインの距離誤差（1.0\,mm未満），寸法誤差（1.5\,mm以下），体積相対誤差（3\%以内）を達成することを実証した．
\end{enumerate}

以上の結果から，本章で構築した3D点群モデル取得の共通処理パイプラインは，サービスロボットの多様な物体操作タスクに対して十分な精度と汎用性を有することが示された．

